"""Phase 2/3 — execute generated SQL and score it (spec §9.2).

Separate from generation (spec §7): re-scoring after a comparison-logic fix costs
ZERO API calls. For each run it executes the extracted SQL read-only against the
working DB copy, executes the gold query on the same DB, compares result sets under
the §9.2 rules, and writes the verdict to `executions`.

  set_match   — order-insensitive, THE primary correctness flag
  exact_match — order-sensitive

Basic error buckets are set here (extraction_failure / timeout / execution_error);
the full structural taxonomy (§9.5: wrong_join, wrong_aggregation, …) lands in Phase 3.

Run:  python scripts/execute_and_score.py [--force]
"""
from __future__ import annotations

import argparse
import functools

import psycopg

from yardstick import comparison, sandbox, spider_data as sd
from yardstick.envtools import require


@functools.lru_cache(maxsize=None)
def gold_rows(db_id: str, gold_sql: str):
    res = sandbox.execute(sd.working_db_path(db_id), gold_sql)
    return res.rows if res.executed else None


def score_run(run) -> dict:
    qid, db_id, gold_sql, extracted_sql = run
    if not extracted_sql:
        return {"executed": False, "error_type": "extraction_failure",
                "set_match": False, "exact_match": False, "timed_out": False,
                "execution_error": None, "result_hash": None,
                "result_row_count": None, "result_col_count": None, "execution_time_ms": None}

    res = sandbox.execute(sd.working_db_path(db_id), extracted_sql)
    if not res.executed:
        return {"executed": False,
                "error_type": "timeout" if res.timed_out else "execution_error",
                "set_match": False, "exact_match": False, "timed_out": res.timed_out,
                "execution_error": res.error, "result_hash": None,
                "result_row_count": None, "result_col_count": None,
                "execution_time_ms": res.execution_time_ms}

    gold = gold_rows(db_id, gold_sql)
    cmp = comparison.compare(res.rows, gold if gold is not None else [])
    return {"executed": True, "error_type": None,
            "set_match": cmp["set_match"], "exact_match": cmp["exact_match"],
            "timed_out": False, "execution_error": None,
            "result_hash": cmp["pred_hash"],
            "result_row_count": res.row_count, "result_col_count": res.col_count,
            "execution_time_ms": res.execution_time_ms}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-score all runs")
    args = ap.parse_args()

    with psycopg.connect(require("DATABASE_URL")) as conn:
        with conn.cursor() as cur:
            where = "" if args.force else \
                "WHERE e.execution_id IS NULL"
            cur.execute(
                f"""SELECT r.run_id, r.question_id, q.db_id, q.gold_sql, r.extracted_sql
                    FROM runs r
                    JOIN questions q ON q.question_id = r.question_id
                    LEFT JOIN executions e ON e.run_id = r.run_id
                    {where}
                    ORDER BY r.run_id""")
            rows = cur.fetchall()

        print(f"Scoring {len(rows)} runs...\n")
        n_match = n_exec = 0
        for run_id, qid, db_id, gold_sql, extracted_sql in rows:
            v = score_run((qid, db_id, gold_sql, extracted_sql))
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO executions (run_id, executed, execution_error, result_hash,
                         result_row_count, result_col_count, exact_match, set_match,
                         execution_time_ms, timed_out, error_type)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (run_id) DO UPDATE SET
                         executed=EXCLUDED.executed, execution_error=EXCLUDED.execution_error,
                         result_hash=EXCLUDED.result_hash, result_row_count=EXCLUDED.result_row_count,
                         result_col_count=EXCLUDED.result_col_count, exact_match=EXCLUDED.exact_match,
                         set_match=EXCLUDED.set_match, execution_time_ms=EXCLUDED.execution_time_ms,
                         timed_out=EXCLUDED.timed_out, error_type=EXCLUDED.error_type""",
                    (run_id, v["executed"], v["execution_error"], v["result_hash"],
                     v["result_row_count"], v["result_col_count"], v["exact_match"],
                     v["set_match"], v["execution_time_ms"], v["timed_out"], v["error_type"]))
            conn.commit()
            n_exec += int(v["executed"])
            n_match += int(v["set_match"])

    print(f"Executed OK: {n_exec}/{len(rows)}   set_match: {n_match}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
