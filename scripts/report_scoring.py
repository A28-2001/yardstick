"""Phase 3/7 — scoring summary: accuracy, silent-failure rate, error taxonomy (spec §9.4, §9.5).

silent_failure_rate = count(executed=true AND set_match=false) / count(all)  — per variant per tier.
A silent failure runs cleanly and returns plausible WRONG numbers; the study's key
secondary metric. Also reports the set_match vs exact_match gap (right data, wrong order).

Reads whatever runs exist, so it is useful mid-build and again on the full matrix.
Run:  python scripts/report_scoring.py
"""
from __future__ import annotations

import psycopg

from yardstick.envtools import require

TIERS = ["simple", "moderate", "complex"]


def main() -> int:
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.variant_id, q.tier,
                   count(*)                                              AS n,
                   sum((e.set_match)::int)                               AS correct,
                   sum((e.executed)::int)                                AS executed,
                   sum((e.executed AND NOT e.set_match)::int)            AS silent,
                   sum((NOT r.extraction_success)::int)                  AS extract_fail,
                   sum((e.exact_match)::int)                             AS exact
            FROM runs r
            JOIN questions q ON q.question_id = r.question_id
            JOIN executions e ON e.run_id = r.run_id
            -- replicate=1 is THE analysed matrix (the pilot's extra replicates 2/3 would
            -- otherwise triple-count 10 questions); error_message IS NULL drops pending
            -- generation failures (daily cap), which are not wrong answers.
            WHERE r.replicate = 1 AND r.error_message IS NULL
            GROUP BY r.variant_id, q.tier
            ORDER BY r.variant_id, q.tier""")
        grid = cur.fetchall()

        cur.execute("""
            SELECT r.variant_id, e.error_type, count(*)
            FROM runs r JOIN executions e ON e.run_id = r.run_id
            WHERE r.replicate = 1 AND r.error_message IS NULL AND e.error_type IS NOT NULL
            GROUP BY r.variant_id, e.error_type
            ORDER BY r.variant_id, count(*) DESC""")
        taxo = cur.fetchall()

    print("Accuracy, silent-failure rate, and set/exact gap (per variant × tier)")
    print(f"  {'var':4} {'tier':9} {'n':>3} {'acc':>6} {'silent':>7} {'sfr':>6} "
          f"{'exact':>6} {'extractFail':>11}")
    for vid, tier, n, correct, executed, silent, ef, exact in grid:
        acc = correct / n if n else 0
        sfr = silent / n if n else 0
        print(f"  {vid:4} {tier:9} {n:3d} {acc:6.2f} {silent:7d} {sfr:6.2f} "
              f"{exact:6d} {ef:11d}")

    print("\nError taxonomy (per variant):")
    cur_v = None
    for vid, et, c in taxo:
        if vid != cur_v:
            print(f"  {vid}:")
            cur_v = vid
        print(f"      {et:22s} {c}")
    if not taxo:
        print("  (no failures yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
