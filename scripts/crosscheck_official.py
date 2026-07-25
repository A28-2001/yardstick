"""Phase 3, cross-validate our scorer against the official Spider scorer (spec §9.3).

For a set of generated predictions we compare OUR set_match verdict against the
official Spider `eval_exec_match` (from third_party/spider_eval/evaluation.py, which
parses each query with the official process_sql and compares executed results).

Every disagreement is printed for inspection. Expected, LEGITIMATE differences:
  - the official exec-match is row-ORDER-SENSITIVE, whereas our set_match sorts rows
    (spec §9.2: order-insensitive unless the gold query has ORDER BY). So we expect
    disagreements on unordered queries, that is our scorer being MORE correct, not a bug.
  - the official parser (process_sql) rejects some valid SQL (e.g. window functions);
    those it simply cannot score, while ours executes them fine.

A disagreement where the OFFICIAL says match but WE say no-match would point at a bug
in our logic, that is the case to hunt for.

Run:  python scripts/crosscheck_official.py [--variant V1] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from yardstick import spider_data as sd
from yardstick.envtools import first_line, require

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "third_party" / "spider_eval"))

# process_sql tokenizes with nltk; make sure its data is present (idempotent).
import nltk  # noqa: E402
for _pkg in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{_pkg}")
    except LookupError:
        nltk.download(_pkg, quiet=True)

from process_sql import Schema, get_schema, get_sql  # noqa: E402
from evaluation import eval_exec_match  # noqa: E402


def official_verdict(db_path, pred_sql, gold_sql):
    """Return (verdict: bool|None, note: str|None). None verdict => couldn't score."""
    try:
        schema = Schema(get_schema(str(db_path)))
    except Exception as e:  # noqa: BLE001
        return None, f"schema_error:{first_line(e)}"
    try:
        g = get_sql(schema, gold_sql)
    except Exception:  # noqa: BLE001
        return None, "gold_parse_error"
    try:
        p = get_sql(schema, pred_sql)
    except Exception:  # noqa: BLE001
        return None, "pred_parse_error"
    try:
        return bool(eval_exec_match(str(db_path), pred_sql, gold_sql, p, g)), None
    except Exception as e:  # noqa: BLE001
        return None, f"exec_error:{first_line(e)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="V1")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.run_id, q.db_id, q.gold_sql, r.extracted_sql, e.set_match, q.gold_sql
               FROM runs r JOIN questions q ON q.question_id=r.question_id
               JOIN executions e ON e.run_id=r.run_id
               WHERE r.variant_id=%s AND r.extracted_sql IS NOT NULL
               ORDER BY r.run_id LIMIT %s""",
            (args.variant, args.limit))
        rows = cur.fetchall()

    agree = disagree = unscorable = 0
    disagreements, unscored = [], []
    for run_id, db_id, gold_sql, pred_sql, our_match, _ in rows:
        verdict, note = official_verdict(sd.db_sqlite_path(db_id), pred_sql, gold_sql)
        if verdict is None:
            unscorable += 1
            unscored.append((run_id, db_id, note))
            continue
        if verdict == bool(our_match):
            agree += 1
        else:
            disagree += 1
            disagreements.append((run_id, db_id, our_match, verdict, gold_sql, pred_sql))

    scored = agree + disagree
    print(f"Cross-check of {len(rows)} {args.variant} predictions vs official eval_exec_match:\n")
    print(f"  scored by both : {scored}")
    print(f"  AGREE          : {agree}/{scored}" + (f"  ({100*agree/scored:.0f}%)" if scored else ""))
    print(f"  disagree       : {disagree}")
    print(f"  unscorable by official (parser/schema limits): {unscorable}")

    if unscored:
        print("\nUnscorable by official scorer:")
        for run_id, db_id, note in unscored:
            print(f"  run {run_id} [{db_id}]: {note}")

    if disagreements:
        print("\nDISAGREEMENTS (investigate each):")
        for run_id, db_id, ours, off, gold, pred in disagreements:
            ordered = "ORDER BY" in gold.upper()
            print(f"\n  run {run_id} [{db_id}]  ours(set_match)={ours}  official={off}  "
                  f"gold_has_ORDER_BY={ordered}")
            print(f"    gold: {' '.join(gold.split())}")
            print(f"    pred: {' '.join(pred.split())}")
    else:
        print("\nNo disagreements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
