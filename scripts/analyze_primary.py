"""Phase 5/7 — primary analysis: few-shot lift (V2 vs V1) per tier (spec §10).

For each tier with data: McNemar's exact test on paired set_match outcomes, the
accuracy difference with a bootstrap 95% CI, and the discordant-pair counts. When more
than one tier is present, Benjamini-Hochberg FDR is applied across the tier p-values
(the three pre-registered primary comparisons). Also prints a 4-variant accuracy +
silent-failure context table.

Uses replicate 1 (the pre-registered single replicate).
Run:  python scripts/analyze_primary.py [--tier complex]
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import psycopg

from yardstick import stats
from yardstick.envtools import require

TIERS = ["simple", "moderate", "complex"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=TIERS)
    args = ap.parse_args()

    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        q = ("""SELECT q.tier, r.variant_id, r.question_id, e.set_match, e.executed
                FROM runs r JOIN questions q ON q.question_id=r.question_id
                JOIN executions e ON e.run_id=r.run_id
                WHERE r.replicate=1""")
        params = []
        if args.tier:
            q += " AND q.tier=%s"; params.append(args.tier)
        cur.execute(q, params)
        rows = cur.fetchall()

    # tier -> question -> variant -> set_match ; and executed flags for silent-fail
    data = defaultdict(lambda: defaultdict(dict))
    executed = defaultdict(lambda: defaultdict(dict))
    for tier, vid, qid, sm, ex in rows:
        data[tier][qid][vid] = int(bool(sm))
        executed[tier][qid][vid] = bool(ex)

    tiers_present = [t for t in TIERS if t in data]

    # 4-variant accuracy + silent-failure context
    print("Accuracy and silent-failure rate by variant × tier (replicate 1)\n")
    print(f"  {'tier':9} " + "".join(f"{v:>16}" for v in ["V1", "V2", "V3", "V4"]))
    for tier in tiers_present:
        cells = []
        for v in ["V1", "V2", "V3", "V4"]:
            outs = [data[tier][q][v] for q in data[tier] if v in data[tier][q]]
            exs = [executed[tier][q][v] for q in data[tier] if v in executed[tier][q]]
            if outs:
                acc = sum(outs) / len(outs)
                silent = sum(1 for q in data[tier]
                             if v in data[tier][q] and executed[tier][q][v]
                             and not data[tier][q][v]) / len(outs)
                cells.append(f"{acc:.2f}/sf{silent:.2f}".rjust(16))
            else:
                cells.append("-".rjust(16))
        print(f"  {tier:9} " + "".join(cells))
    print("  (acc = set_match rate; sf = silent-failure rate)\n")

    # Primary comparison V2 vs V1 per tier
    print("PRIMARY: few-shot lift V2 vs V1 (McNemar exact, paired), by tier\n")
    results, pvals = [], []
    for tier in tiers_present:
        qs = [q for q in data[tier] if "V1" in data[tier][q] and "V2" in data[tier][q]]
        a = [data[tier][q]["V1"] for q in qs]   # control
        b = [data[tier][q]["V2"] for q in qs]   # treatment
        res = stats.compare_paired(a, b)
        results.append((tier, res)); pvals.append(res.p_value)
        print(f"  {tier} (n={res.n} paired)")
        print(f"    V1 acc={res.acc_a:.3f}  V2 acc={res.acc_b:.3f}  "
              f"diff={res.diff_pts:+.1f} pts  95% CI [{res.ci_low_pts:+.1f}, {res.ci_high_pts:+.1f}]")
        print(f"    discordant: V1-only={res.a_only}  V2-only={res.b_only}  "
              f"(both correct={res.both_correct}, both wrong={res.both_wrong})")
        print(f"    McNemar exact p = {res.p_value:.4f}\n")

    if len(pvals) > 1:
        reject, p_adj = stats.benjamini_hochberg(pvals)
        print("Benjamini-Hochberg FDR across the primary comparisons (α=0.05):")
        for (tier, _), p, pa, rj in zip(results, pvals, p_adj, reject):
            print(f"  {tier:9} raw p={p:.4f}  adj p={pa:.4f}  "
                  f"{'SIGNIFICANT' if rj else 'not significant'}")
    elif len(pvals) == 1:
        print("(Single tier — BH correction applies once all three primary tiers are run.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
