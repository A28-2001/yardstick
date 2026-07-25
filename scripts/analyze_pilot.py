"""Phase 4, pilot analysis: variance, ceiling/floor, failure rates, power (spec §10.3, §10.5).

Reports the four things the pre-registration needs before the full run:
  1. Replicate variance, does set_match ever differ across the 3 replicates? If not,
                            drop to 1 replicate for the full run (saves ~2/3 of tokens).
  2. Ceiling / floor, simple tier >~92% (no room to detect lift) or complex <~15%.
  3. Extraction / timeout, failure rates that would invalidate the run.
  4. Power. V2 vs V1 effect size & n_required per tier, plus the minimum
                            detectable effect at n=50 (conservative unpaired approximation;
                            the paired McNemar design needs fewer).

Run:  python scripts/analyze_pilot.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
PILOT_FILE = REPO / "configs" / "pilot_questions.json"
TIERS = ["simple", "moderate", "complex"]
CEILING, FLOOR = 0.92, 0.15


def main() -> int:
    ids = json.loads(PILOT_FILE.read_text())["question_ids"]
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.question_id, q.tier, r.variant_id, r.replicate,
                   e.set_match, e.executed, e.timed_out, r.extraction_success
            FROM runs r
            JOIN questions q ON q.question_id = r.question_id
            JOIN executions e ON e.run_id = r.run_id
            WHERE r.question_id = ANY(%s)
            ORDER BY r.variant_id, r.question_id, r.replicate""", (ids,))
        rows = cur.fetchall()

    # index
    by_cell = defaultdict(dict)     # (variant, qid) -> {replicate: set_match}
    tier_of = {}
    n_extract_fail = n_timeout = n_total = 0
    replicates_seen = set()
    for qid, tier, vid, rep, sm, ex, to, extr in rows:
        by_cell[(vid, qid)][rep] = bool(sm)
        tier_of[qid] = tier
        replicates_seen.add(rep)
        n_total += 1
        n_extract_fail += int(not extr)
        n_timeout += int(bool(to))

    print(f"Pilot: {len(ids)} questions, replicates present: {sorted(replicates_seen)}, "
          f"{n_total} run-rows\n")

    # 1. replicate variance
    disagreeing = [cell for cell, reps in by_cell.items()
                   if len(reps) > 1 and len(set(reps.values())) > 1]
    multi = [cell for cell, reps in by_cell.items() if len(reps) > 1]
    print("1) REPLICATE VARIANCE")
    print(f"   cells with >1 replicate: {len(multi)}")
    print(f"   cells where set_match DIFFERS across replicates: {len(disagreeing)}")
    if not disagreeing:
        print("   -> zero variance at temp 0. DECISION: use 1 replicate for the full run.\n")
    else:
        for vid, qid in disagreeing:
            print(f"     {vid} {qid}: {by_cell[(vid,qid)]}")
        print()

    # accuracy per (variant, tier) using replicate 1
    def acc(vid, tier):
        vals = [reps.get(1) for (v, qid), reps in by_cell.items()
                if v == vid and tier_of[qid] == tier and 1 in reps]
        vals = [x for x in vals if x is not None]
        return (sum(vals) / len(vals), len(vals)) if vals else (float("nan"), 0)

    variants = sorted({v for v, _ in by_cell})
    print("2) ACCURACY per variant × tier (replicate 1), with ceiling/floor flags")
    print("   " + "tier".ljust(9) + "".join(v.ljust(8) for v in variants))
    tier_acc = {}
    for tier in TIERS:
        cells = []
        for v in variants:
            a, n = acc(v, tier)
            tier_acc[(v, tier)] = a
            cells.append(f"{a:.2f}({n})".ljust(8))
        print("   " + tier.ljust(9) + "".join(cells))
    for tier in TIERS:
        accs = [tier_acc[(v, tier)] for v in variants if not np.isnan(tier_acc[(v, tier)])]
        if accs and tier == "simple" and min(accs) >= CEILING:
            print(f"   ⚠ CEILING on simple: all variants ≥ {CEILING:.0%}, little room to detect lift.")
        if accs and tier == "complex" and max(accs) <= FLOOR:
            print(f"   ⚠ FLOOR on complex: all variants ≤ {FLOOR:.0%}.")
    print()

    # 3. failure rates
    print("3) FAILURE RATES")
    print(f"   extraction failures: {n_extract_fail}/{n_total} ({n_extract_fail/max(n_total,1):.1%})")
    print(f"   timeouts:            {n_timeout}/{n_total} ({n_timeout/max(n_total,1):.1%})\n")

    # 4. power: V2 vs V1 per tier
    print("4) POWER, primary comparison V2 (few-shot) vs V1 (zero-shot), 8B, per tier")
    analysis = NormalIndPower()
    for tier in TIERS:
        p1 = tier_acc.get(("V1", tier)); p2 = tier_acc.get(("V2", tier))
        if p1 is None or p2 is None or np.isnan(p1) or np.isnan(p2):
            print(f"   {tier:9s}: insufficient data"); continue
        h = proportion_effectsize(p2, p1)
        if abs(h) < 1e-6:
            print(f"   {tier:9s}: V1={p1:.2f} V2={p2:.2f}  effect≈0 -> no difference to detect in pilot")
            continue
        n_req = analysis.solve_power(effect_size=abs(h), alpha=0.05, power=0.8,
                                     alternative="two-sided")
        print(f"   {tier:9s}: V1={p1:.2f} V2={p2:.2f}  Cohen_h={h:+.3f}  "
              f"n/group for 80% power ≈ {n_req:.0f}")

    # minimum detectable effect at n=50 (unpaired, conservative)
    mde_h = analysis.solve_power(nobs1=50, alpha=0.05, power=0.8, alternative="two-sided")
    print(f"\n   Minimum detectable effect at n=50 (unpaired, α=.05, power=.8): Cohen_h ≈ {mde_h:.3f}")
    for base in (0.5, 0.7, 0.85):
        # find delta above `base` giving this h
        p2 = np.sin(np.arcsin(np.sqrt(base)) + mde_h / 2) ** 2
        print(f"     at baseline {base:.0%}: detectable if treatment ≥ ~{p2:.0%} "
              f"(Δ ≈ {p2-base:+.0%} pts)")
    print("\n   NOTE: this is the conservative unpaired approximation; the paired McNemar")
    print("   test used for the primary analysis needs FEWER samples for the same power.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
