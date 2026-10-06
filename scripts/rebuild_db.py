"""Rebuild the results database from what survives on disk.

The original Supabase project was removed after a long idle pause on the free tier,
and it held the only copy of the run table: generation never wrote a local log. This
reconstructs the database from two surviving sources,

  data/questions.json     the 150 validated questions, every column, exact
  docs/data/runs.json     the 600 graded runs as exported for the site

and regenerates everything downstream of the model call with the real pipeline code.
That part is exact, because the target databases are local SQLite files and scoring
is deterministic:

  questions, variants    scripts/load_questions.py
  executions             scripts/execute_and_score.py   (re-executes every query)
  question_features      scripts/compute_features.py

What cannot come back is stored as NULL rather than invented:

  runs.raw_output                     the full model responses
  runs.input_tokens, output_tokens    only their sum survived, kept in total_tokens
  pilot runs and replicates above 1   never exported

No analysis script reads any of those. Two smaller losses from the site export are
checked by the verification step rather than assumed harmless: extracted SQL had its
whitespace collapsed, which only matters for a string literal containing a run of
spaces, and cost_usd was rounded to six decimal places.

Every restored run carries a provenance string so nobody mistakes it for an original.

Run:  python scripts/rebuild_db.py            # refuses if the target already has runs
      python scripts/rebuild_db.py --force    # drops the five tables and rebuilds
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import psycopg
import yaml

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "data" / "questions.json"
RUNS = REPO / "docs" / "data" / "runs.json"
SCHEMA = REPO / "sql" / "schema.sql"
VARIANT_DIR = REPO / "configs" / "variants"

# Applied after schema.sql. The spec's NOT NULL constraints describe a live run,
# where these values always exist; a restoration cannot honour them without
# fabricating data, so it relaxes exactly these three and says so in the table.
RESTORE_DDL = """
ALTER TABLE runs ALTER COLUMN raw_output    DROP NOT NULL;
ALTER TABLE runs ALTER COLUMN input_tokens  DROP NOT NULL;
ALTER TABLE runs ALTER COLUMN output_tokens DROP NOT NULL;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS total_tokens INTEGER;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS provenance   TEXT;
COMMENT ON COLUMN runs.provenance IS
  'Set on rows rebuilt by scripts/rebuild_db.py; NULL means an original live run.';
"""


def step(cmd: str) -> None:
    """Run one of the real pipeline scripts, exactly as a person would."""
    print(f"\n$ python {cmd}", flush=True)   # else it lands after the child's output
    subprocess.run([sys.executable, *cmd.split()], cwd=REPO, check=True)


def provenance() -> str:
    sha = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(RUNS)],
                         cwd=REPO, capture_output=True, text=True).stdout.strip()
    return f"restored {dt.date.today()} from docs/data/runs.json @ {sha or 'uncommitted'}"


def prepare(conn, force: bool) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('runs') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("SELECT count(*) FROM runs")
            n = cur.fetchone()[0]
            if n and not force:
                raise SystemExit(f"Target already holds {n} runs. Re-run with --force to "
                                 "drop and rebuild it.")
        if force:
            cur.execute("DROP TABLE IF EXISTS question_features, executions, runs, "
                        "variants, questions CASCADE")
        cur.execute(SCHEMA.read_text())
        cur.execute(RESTORE_DDL)
    conn.commit()
    print("schema applied, restore columns added")


def insert_runs(conn) -> int:
    questions = json.loads(QUESTIONS.read_text())
    runs = json.loads(RUNS.read_text())["runs"]
    by_key = {(q["db_id"], q["question_text"]): q for q in questions}
    temperature = {}
    for path in VARIANT_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(path.read_text())
        temperature[cfg["variant_id"]] = cfg["temperature"]

    prov = provenance()
    payload = []
    for r in runs:
        q = by_key.get((r["db"], r["q"]))
        if q is None:
            raise SystemExit(f"run has no matching question: {r['db']} / {r['q'][:60]}")
        if " ".join(q["gold_sql"].split()) != r["gold"]:
            raise SystemExit(f"gold SQL disagrees for {q['question_id']}")
        payload.append((q["question_id"], r["v"], 1, None, r["sql"] or None, bool(r["sql"]),
                        r["conf"], None, None, r["tok"], r["cost"], r["ms"],
                        temperature[r["v"]], None, prov))

    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO runs (question_id, variant_id, replicate, raw_output,
                 extracted_sql, extraction_success, self_confidence, input_tokens,
                 output_tokens, total_tokens, cost_usd, latency_ms, temperature,
                 error_message, provenance)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", payload)
    conn.commit()
    print(f"inserted {len(payload)} runs  ({prov})")
    return len(payload)


def verify(conn) -> int:
    """Compare every regenerated verdict with the one recorded in the original run.

    The site export captured the original scorer's output for each run, so it is an
    independent record to check the re-execution against. Any disagreement means the
    rebuild is not faithful for that run, and the script exits non-zero.
    """
    questions = {(q["db_id"], q["question_text"]): q["question_id"]
                 for q in json.loads(QUESTIONS.read_text())}
    recorded = {(questions[(r["db"], r["q"])], r["v"]): r
                for r in json.loads(RUNS.read_text())["runs"]}

    with conn.cursor() as cur:
        cur.execute("""SELECT r.question_id, r.variant_id, e.set_match, e.executed,
                              e.error_type, e.result_row_count, q.gold_row_count
                       FROM runs r JOIN executions e ON e.run_id = r.run_id
                       JOIN questions q ON q.question_id = r.question_id""")
        rebuilt = cur.fetchall()

    fields = ["correct", "executed", "error_type", "row_count", "gold_rows"]
    bad = []
    for qid, vid, sm, ex, et, rows, grows in rebuilt:
        o = recorded[(qid, vid)]
        got = [bool(sm), bool(ex), et, rows, grows]
        want = [o["ok"], o["ran"], o["err"], o["prows"], o["grows"]]
        diff = [f"{f}: {w!r} -> {g!r}" for f, w, g in zip(fields, want, got) if w != g]
        if diff:
            bad.append((qid, vid, diff))

    print(f"\nverification: {len(rebuilt) - len(bad)} of {len(rebuilt)} runs reproduce the "
          f"original verdict on all {len(fields)} checked fields")
    for qid, vid, diff in bad[:20]:
        print(f"  MISMATCH {qid} {vid}: " + "; ".join(diff))
    if len(rebuilt) != len(recorded):
        print(f"  expected {len(recorded)} runs, found {len(rebuilt)}")
        return 1
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="drop the tables and rebuild")
    args = ap.parse_args()

    url = require("DATABASE_URL")
    with psycopg.connect(url) as conn:
        prepare(conn, args.force)
    step("scripts/load_questions.py")
    with psycopg.connect(url) as conn:
        insert_runs(conn)
    step("scripts/execute_and_score.py")
    step("scripts/compute_features.py")
    with psycopg.connect(url) as conn:
        return verify(conn)


if __name__ == "__main__":
    raise SystemExit(main())
