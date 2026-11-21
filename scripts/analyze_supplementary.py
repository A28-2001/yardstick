"""Supplementary numbers cited on the site, report and README, each reproducible here.

These came out of a claims audit (CLAIMS.md): figures that were stated in the prose but
computed by no script, plus checks that replaced overstated wording. Everything is
deterministic: rows are sorted by question id before any seeded resampling, so the
output does not depend on the order the database returns rows in.

Prints only. It writes nothing to results/, which holds the published record.

Run:  python scripts/analyze_supplementary.py      (needs DATABASE_URL, see rebuild_db.py)
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
from scipy.stats import binomtest, fisher_exact
from sklearn.metrics import roc_auc_score

from yardstick import calibration as cal
from yardstick import routing
from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
VARIANTS = ["V1", "V2", "V3", "V4"]
LARGE = {"V3", "V4"}
SEED = 20260721
PRICE = {"V1": (0.05, 0.08), "V2": (0.05, 0.08),      # $ per million tokens, in / out,
         "V3": (0.59, 0.79), "V4": (0.59, 0.79)}      # from configs/pricing.yaml


def load(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT r.question_id, r.variant_id, e.set_match, e.executed, e.result_hash,
                   r.self_confidence, e.error_type, e.result_row_count, r.cost_usd,
                   COALESCE(r.input_tokens + r.output_tokens, r.total_tokens),
                   length(r.extracted_sql), length(q.gold_sql), length(q.question_text)
            FROM runs r JOIN executions e ON e.run_id = r.run_id
            JOIN questions q ON q.question_id = r.question_id
            WHERE r.replicate = 1 AND r.error_message IS NULL
            ORDER BY r.question_id, r.variant_id""")
        rows = cur.fetchall()
    per_q = defaultdict(dict)
    for q, v, sm, ex, h, cf, et, rc, cost, tok, ls, lg, lq in rows:
        per_q[q][v] = dict(ok=bool(sm), ex=bool(ex), h=h, conf=float(cf), err=et, rows=rc,
                           cost=float(cost), tok=tok, short=(ex and (ls or 0) < 190
                                                             and lg < 190 and lq < 120))
    return per_q


def section(title):
    print(f"\n{title}")


def main() -> int:
    with psycopg.connect(require("DATABASE_URL")) as conn:
        per_q = load(conn)
        rdf = routing.load_routing_data(conn)
    qs = sorted(per_q)
    outs = [(q, v, per_q[q][v]) for q in qs for v in VARIANTS if v in per_q[q]]
    wrong = [o for o in outs if not o[2]["ok"]]

    section("1) Silent mistakes")
    s = sum(o[2]["ex"] for o in wrong)
    ci = binomtest(s, len(wrong)).proportion_ci()
    print(f"   {s} of {len(wrong)} mistakes ran without an error = {s/len(wrong):.1%}, "
          f"95% CI [{ci.low:.1%}, {ci.high:.1%}]")
    lg = [o for o in wrong if o[1] in LARGE]; sm = [o for o in wrong if o[1] not in LARGE]
    sl, ss = sum(o[2]["ex"] for o in lg), sum(o[2]["ex"] for o in sm)
    _, p = fisher_exact([[sl, len(lg) - sl], [ss, len(sm) - ss]])
    print(f"   large model {sl}/{len(lg)}, small model {ss}/{len(sm)}, Fisher exact p = {p:.3f}")
    hi = sum(o[2]["conf"] >= 0.9 for o in wrong)
    print(f"   mistakes stated at confidence >= 0.9: {hi} of {len(wrong)}; "
          f"all outputs: {sum(o[2]['conf'] >= 0.9 for o in outs)} of {len(outs)}")
    loud = [o for o in wrong if not o[2]["ex"]]
    print(f"   loud mistakes {len(loud)}, all schema_error: "
          f"{all(o[2]['err'] == 'schema_error' for o in loud)}")
    print(f"   10,000-row cap hit by: {[(o[1], o[0]) for o in outs if o[2]['rows'] == 10000]}")

    section("2) Cross-check: flag a question when the four setups do not all return the same rows")
    agree = {q: cal.pairwise_agreement([d["h"] for d in per_q[q].values() if d["ex"]]) for q in qs}
    flag = {q: np.nan_to_num(agree[q], nan=1.0) < 1.0 for q in qs}
    right = [o for o in outs if o[2]["ok"]]
    caught = sum(flag[o[0]] for o in wrong); false = sum(flag[o[0]] for o in right)
    print(f"   questions flagged {sum(flag.values())} of {len(qs)}; outputs flagged "
          f"{sum(flag[o[0]] for o in outs)} of {len(outs)}")
    print(f"   mistakes caught {caught} of {len(wrong)}; correct outputs flagged {false} of {len(right)}")
    print(f"   unflagged questions {sum(not f for f in flag.values())}, holding "
          f"{sum(not flag[o[0]] for o in wrong)} mistakes")
    rec, spec = caught / len(wrong), 1 - false / len(right)
    print(f"   balanced accuracy, all outputs: {(rec + spec) / 2:.1%}")
    pw = [o for o in wrong if o[2]["short"]]; pr = [o for o in right if o[2]["short"]]
    bq = (np.mean([flag[o[0]] for o in pw]) + 1 - np.mean([flag[o[0]] for o in pr])) / 2
    print(f"   balanced accuracy, quiz pool ({len(pw)} silent, {len(pr)} correct): {bq:.1%}")

    section("3) Agreement vs confidence, AUC, 95% bootstrap CI over questions")
    def aucs(sample):
        y, a, c = [], [], []
        for q in sample:
            for d in per_q[q].values():
                y.append(int(d["ok"])); a.append(np.nan_to_num(agree[q], nan=1.0)); c.append(d["conf"])
        return roc_auc_score(y, a), roc_auc_score(y, c)
    base = aucs(qs)
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(2000):
        a, c = aucs([qs[i] for i in rng.integers(0, len(qs), len(qs))])
        diffs.append(a - c)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"   agreement {base[0]:.3f}, confidence {base[1]:.3f}, gap {base[0]-base[1]:.3f} "
          f"[{lo:.3f}, {hi:.3f}]")

    section("4) Confidence on right vs wrong answers, per variant")
    for v in VARIANTS:
        r = [o[2]["conf"] for o in outs if o[1] == v and o[2]["ok"]]
        w = [o[2]["conf"] for o in outs if o[1] == v and not o[2]["ok"]]
        print(f"   {v}: right {np.mean(r):.3f}, wrong {np.mean(w):.3f}")

    section("5) Random routing at the router's budget, 100,000 draws (test split)")
    test = rdf[rdf.split == "test"].sort_values("question_id").reset_index(drop=True)
    cheap, strong = test.cheap_correct.to_numpy(), test.strong_correct.to_numpy()
    n, k = len(test), int((~cheap.astype(bool)).sum())
    rng = np.random.default_rng(SEED)
    draws = np.empty(100_000)
    for i in range(len(draws)):
        m = np.zeros(n, bool); m[rng.choice(n, size=k, replace=False)] = True
        draws[i] = np.where(m, strong, cheap).mean()
    print(f"   n = {n}, k = {k}: mean {draws.mean():.4f}, 95% of draws in "
          f"[{np.percentile(draws, 2.5):.4f}, {np.percentile(draws, 97.5):.4f}], "
          f"draws >= 0.7833: {(draws >= 0.7833 - 1e-9).mean():.1%}")

    section("6) What drives cost vs difficulty (Pearson r, all 150 questions)")
    hard = 1 - rdf.cheap_correct.astype(float); cost = rdf.cheap_cost.astype(float)
    for col in ["question_token_count", "schema_table_count", "schema_column_count"]:
        x = rdf[col].astype(float)
        print(f"   {col:22} vs cost {np.corrcoef(x, cost)[0,1]:.2f}, vs cheap model failing "
              f"{np.corrcoef(x, hard)[0,1]:.2f}")

    section("7) Input share, recovered from each run's cost and token total")
    tin = tout = cin = cout = 0.0
    for q, v, d in outs:
        pi, po = PRICE[v]; c, t = d["cost"] * 1e6, d["tok"]
        i = (c - t * po) / (pi - po); o = t - i
        tin += i; tout += o; cin += i * pi; cout += o * po
    print(f"   input is {tin/(tin+tout):.1%} of tokens and {cin/(cin+cout):.1%} of spend "
          f"(600 runs, list price ${sum(d['cost'] for _, _, d in outs):.4f})")

    section("8) Benjamini Hochberg across the six model comparisons (results/model_effect.csv)")
    me = list(csv.DictReader(open(REPO / "results" / "model_effect.csv")))
    ps = np.array([float(r["mcnemar_p"]) for r in me]); order = np.argsort(ps); m = len(ps)
    adj = np.empty(m); run = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]; run = min(run, ps[i] * m / rank); adj[i] = run
    for r, a in zip(me, adj):
        print(f"   {r['tier']:9} {r['comparison']:15} raw p {float(r['mcnemar_p']):.4f}  adjusted {a:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
