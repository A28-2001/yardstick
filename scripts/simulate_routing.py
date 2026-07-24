"""Phase 8 — simulate routing policies on the TEST split (spec §11.6, §11.7).

Every variant ran on every question, so the counterfactual matrix is complete and each
policy is just a selection from a table we already have — ZERO extra API calls (§11.1).

Policies: always_cheap, always_expensive, random, length_only, difficulty_routed, oracle.
Reported per policy: accuracy, total cost, accuracy retained vs always-expensive, cost
relative to always-expensive, and the fraction of the ORACLE's available savings captured.
Also sweeps the routing threshold to produce the accuracy-cost curve (§11.7).

The predictor is trained on the TRAIN split only and evaluated on TEST only (§11.2), so
the routing evaluation is not circular.

Run:  python scripts/simulate_routing.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import psycopg

from yardstick import routing
from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
SEED = 20260721


def evaluate(test, use_strong: np.ndarray) -> tuple[float, float]:
    """Accuracy and total cost when `use_strong[i]` decides the model for question i."""
    correct = np.where(use_strong, test["strong_correct"], test["cheap_correct"])
    cost = np.where(use_strong, test["strong_cost"], test["cheap_cost"])
    return float(correct.mean()), float(cost.sum())


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    with psycopg.connect(require("DATABASE_URL")) as conn:
        df = routing.load_routing_data(conn)
    train, test = df[df.split == "train"], df[df.split == "test"].reset_index(drop=True)
    n = len(test)
    rng = np.random.default_rng(SEED)

    # predictors (trained on TRAIN only)
    p_full = routing.fit_predict_proba(train, test, routing.ROUTER_FEATURES)
    p_len = routing.fit_predict_proba(train, test, routing.LENGTH_ONLY)

    always_cheap = np.zeros(n, bool)
    always_strong = np.ones(n, bool)
    # oracle: use cheap when cheap already gets it right, else strong (perfect foresight)
    oracle = ~test["cheap_correct"].to_numpy().astype(bool)

    # route the top-k most-likely-hard questions, k matched to the oracle's escalation rate
    k = int(oracle.sum())
    def top_k(p):
        m = np.zeros(n, bool)
        if k:
            m[np.argsort(-p)[:k]] = True
        return m
    random_pol = np.zeros(n, bool)
    random_pol[rng.choice(n, size=k, replace=False)] = True

    policies = {
        "always_cheap": always_cheap,
        "always_expensive": always_strong,
        "random": random_pol,
        "length_only": top_k(p_len),
        "difficulty_routed": top_k(p_full),
        "oracle": oracle,
    }

    acc_ae, cost_ae = evaluate(test, always_strong)
    acc_ac, cost_ac = evaluate(test, always_cheap)
    oracle_acc, oracle_cost = evaluate(test, oracle)
    # savings the oracle achieves vs always-expensive (in $)
    oracle_savings = cost_ae - oracle_cost

    # Matched-budget policies escalate the same k questions, so cost-savings comparisons
    # are only meaningful among THOSE. (A cost-only "savings captured" number is gameable:
    # always_cheap trivially "saves" the most while giving up the most accuracy.)
    matched = {"random", "length_only", "difficulty_routed"}

    print(f"Routing simulation on the TEST split (n={n}); escalation budget k={k} "
          f"({k/n:.0%} of questions)\n")
    print(f"  {'policy':20} {'acc':>6} {'cost($)':>10} {'acc vs exp':>11} "
          f"{'cost vs exp':>12} {'acc gap vs oracle':>18} {'oracle $ saved':>15}")
    rows = []
    for name, mask in policies.items():
        acc, cost = evaluate(test, mask)
        acc_ret = acc / acc_ae * 100 if acc_ae else float("nan")
        cost_rel = cost / cost_ae * 100 if cost_ae else float("nan")
        gap_pts = (acc - oracle_acc) * 100
        captured = (((cost_ae - cost) / oracle_savings * 100)
                    if (oracle_savings > 0 and name in matched) else float("nan"))
        cap_str = f"{captured:14.1f}%" if not np.isnan(captured) else f"{'—':>15}"
        print(f"  {name:20} {acc:6.3f} {cost:10.5f} {acc_ret:10.1f}% {cost_rel:11.1f}% "
              f"{gap_pts:17.1f} {cap_str}")
        rows.append([name, round(acc, 4), round(cost, 6), round(acc_ret, 1),
                     round(cost_rel, 1), round(gap_pts, 1),
                     (round(captured, 1) if not np.isnan(captured) else ""), int(mask.sum())])

    with (RESULTS / "routing_comparison.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["policy", "accuracy", "total_cost_usd", "acc_pct_of_always_expensive",
                    "cost_pct_of_always_expensive", "acc_gap_vs_oracle_pts",
                    "pct_of_oracle_savings_captured_matched_budget_only", "n_escalated"])
        w.writerows(rows)
    print(f"\n  wrote results/routing_comparison.csv")

    # threshold sweep (accuracy-cost curve) — a curve is an analysis, a point is a claim
    sweep = []
    for thr in np.linspace(0, 1, 51):
        mask = p_full >= thr
        acc, cost = evaluate(test, mask)
        sweep.append([round(float(thr), 3), round(acc, 4), round(cost, 6), int(mask.sum())])
    with (RESULTS / "routing_threshold_sweep.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["threshold", "accuracy", "total_cost_usd", "n_escalated"])
        w.writerows(sweep)
    print(f"  wrote results/routing_threshold_sweep.csv ({len(sweep)} points)")

    print(f"\n  reference: always_cheap acc={acc_ac:.3f} cost=${cost_ac:.5f} | "
          f"always_expensive acc={acc_ae:.3f} cost=${cost_ae:.5f}")
    print(f"  oracle: acc={oracle_acc:.3f} cost=${oracle_cost:.5f} "
          f"(available savings vs always-expensive: ${oracle_savings:.5f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
