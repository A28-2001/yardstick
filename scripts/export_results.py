"""Phase 7/10 — export analysis tables to results/*.csv (spec §15).

Writes the CSVs the write-up and the Looker Studio dashboard consume. Every number
comes from the same yardstick.stats functions the console analyses use, so the CSVs
and the printed analyses cannot disagree. Uses replicate 1, valid generations only.

Produces:
  accuracy_by_variant_tier.csv, silent_failures.csv, error_taxonomy.csv,
  primary_analysis.csv, model_effect.csv, interaction.csv, query_efficiency.csv

Run:  python scripts/export_results.py
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import psycopg

from yardstick import stats
from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
TIERS = ["simple", "moderate", "complex"]
VARIANTS = ["V1", "V2", "V3", "V4"]


def write_csv(name, header, rows):
    path = RESULTS / name
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  wrote {path.relative_to(REPO)} ({len(rows)} rows)")


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        # per variant×tier aggregate (valid generations only)
        cur.execute("""
            SELECT r.variant_id, q.tier, count(*) n,
                   sum((e.set_match)::int) correct,
                   sum((e.executed AND NOT e.set_match)::int) silent,
                   sum((e.exact_match)::int) exact
            FROM runs r JOIN questions q ON q.question_id=r.question_id
            JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL
            GROUP BY r.variant_id, q.tier""")
        agg = cur.fetchall()

        cur.execute("""
            SELECT r.variant_id, q.tier, e.error_type, count(*)
            FROM runs r JOIN questions q ON q.question_id=r.question_id
            JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL AND e.error_type IS NOT NULL
            GROUP BY r.variant_id, q.tier, e.error_type""")
        taxo = cur.fetchall()

        # per-variant summary: accuracy, silent share OF ERRORS, confidence behaviour
        cur.execute("""
            SELECT r.variant_id, count(*) n,
                   avg((e.set_match)::int)                                  accuracy,
                   count(*) FILTER (WHERE NOT e.set_match)                  n_errors,
                   count(*) FILTER (WHERE NOT e.set_match AND e.executed)   n_silent,
                   avg(r.self_confidence)                                   mean_conf,
                   avg(r.self_confidence) FILTER (WHERE NOT e.set_match)    conf_when_wrong
            FROM runs r JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL
            GROUP BY r.variant_id ORDER BY r.variant_id""")
        summary = cur.fetchall()

        # per-question outcomes for paired stats
        cur.execute("""
            SELECT q.tier, r.variant_id, r.question_id, e.set_match, e.execution_time_ms
            FROM runs r JOIN questions q ON q.question_id=r.question_id
            JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL""")
        sm = defaultdict(lambda: defaultdict(dict))
        et = defaultdict(lambda: defaultdict(dict))
        for t, v, qid, s, ems in cur.fetchall():
            sm[t][qid][v] = int(bool(s))
            if s and ems is not None:
                et[t][qid][v] = float(ems)

    print("Exporting results CSVs (replicate 1, valid generations):")

    # 1. accuracy_by_variant_tier
    rows = []
    for vid, tier, n, correct, silent, exact in agg:
        rows.append([vid, tier, n, round(correct / n, 4), round(silent / n, 4),
                     round(exact / n, 4)])
    write_csv("accuracy_by_variant_tier.csv",
              ["variant", "tier", "n", "accuracy", "silent_failure_rate", "exact_match_rate"],
              sorted(rows))

    # 2. silent_failures
    write_csv("silent_failures.csv", ["variant", "tier", "n", "silent_failures", "silent_failure_rate"],
              sorted([[v, t, n, s, round(s / n, 4)] for v, t, n, _, s, _ in agg]))

    # 3. error_taxonomy
    write_csv("error_taxonomy.csv", ["variant", "tier", "error_type", "count"],
              sorted([[v, t, et_, c] for v, t, et_, c in taxo]))

    # 3b. per-variant summary (drives the report figures)
    write_csv("variant_summary.csv",
              ["variant", "n", "accuracy", "n_errors", "n_silent_errors",
               "silent_share_of_errors", "mean_confidence", "confidence_when_wrong"],
              [[v, n, round(float(a), 4), ne, ns,
                round(ns / ne, 4) if ne else None,
                round(float(mc), 4) if mc is not None else None,
                round(float(cw), 4) if cw is not None else None]
               for v, n, a, ne, ns, mc, cw in summary])

    def paired(tier, va, vb):
        qs = [q for q in sm[tier] if va in sm[tier][q] and vb in sm[tier][q]]
        return [sm[tier][q][va] for q in qs], [sm[tier][q][vb] for q in qs]

    # 4. primary_analysis (V2 vs V1) with BH
    prim, pvals = [], []
    for tier in TIERS:
        if tier not in sm:
            continue
        a, b = paired(tier, "V1", "V2")
        if not a:
            continue
        r = stats.compare_paired(a, b)
        prim.append([tier, r.n, round(r.acc_a, 4), round(r.acc_b, 4), round(r.diff_pts, 1),
                     round(r.ci_low_pts, 1), round(r.ci_high_pts, 1), round(r.p_value, 4)])
        pvals.append(r.p_value)
    if len(pvals) > 1:
        _, p_adj = stats.benjamini_hochberg(pvals)
    else:
        p_adj = pvals
    for row, pa in zip(prim, p_adj):
        row.append(round(pa, 4))
    write_csv("primary_analysis.csv",
              ["tier", "n", "v1_acc", "v2_acc", "diff_pts", "ci_low_pts", "ci_high_pts",
               "mcnemar_p", "bh_adj_p"], prim)

    # 5. model_effect (V3 vs V1, V4 vs V2)
    me = []
    for tier in TIERS:
        if tier not in sm:
            continue
        for label, va, vb in [("model_zeroshot", "V1", "V3"), ("model_fewshot", "V2", "V4")]:
            a, b = paired(tier, va, vb)
            if not a:
                continue
            r = stats.compare_paired(a, b)
            me.append([tier, label, r.n, round(r.acc_a, 4), round(r.acc_b, 4),
                       round(r.diff_pts, 1), round(r.ci_low_pts, 1), round(r.ci_high_pts, 1),
                       round(r.p_value, 4)])
    write_csv("model_effect.csv",
              ["tier", "comparison", "n", "acc_a", "acc_b", "diff_pts", "ci_low_pts",
               "ci_high_pts", "mcnemar_p"], me)

    # 6. interaction (DiD)
    inter = []
    for tier in TIERS:
        if tier not in sm:
            continue
        qs = [q for q in sm[tier] if all(v in sm[tier][q] for v in VARIANTS)]
        if not qs:
            continue
        v = {k: [sm[tier][q][k] for q in qs] for k in VARIANTS}
        pt, lo, hi = stats.diff_in_diff(v["V1"], v["V2"], v["V3"], v["V4"])
        inter.append([tier, len(qs), round(pt, 1), round(lo, 1), round(hi, 1)])
    write_csv("interaction.csv", ["tier", "n", "did_pts", "ci_low_pts", "ci_high_pts"], inter)

    # 7. query_efficiency (correct queries only)
    qe = []
    for tier in TIERS:
        if tier not in et:
            continue
        for vv in VARIANTS:
            times = [et[tier][q][vv] for q in et[tier] if vv in et[tier][q]]
            if times:
                qe.append([vv, tier, len(times), round(statistics.median(times), 1)])
    write_csv("query_efficiency.csv", ["variant", "tier", "n_correct", "median_exec_ms"],
              sorted(qe))

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
