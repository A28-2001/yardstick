"""Phase 1, Step 5, load validated questions + variants into Supabase.

Reads data/questions.json (from sample_and_validate.py) and the 4 variant YAML
configs, and upserts them into the `questions` and `variants` tables. Idempotent.

Run:  python scripts/load_questions.py
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import yaml

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "data" / "questions.json"
VARIANT_DIR = REPO / "configs" / "variants"

Q_COLS = ["question_id", "db_id", "question_text", "gold_sql", "gold_result_hash",
          "gold_row_count", "gold_col_count", "spider_difficulty", "tier",
          "schema_ddl", "split"]


def load_variants(cur) -> int:
    n = 0
    for path in sorted(VARIANT_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text())
        cur.execute(
            """INSERT INTO variants (variant_id, prompt_strategy, model, prompt_version, config_path)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (variant_id) DO UPDATE SET
                 prompt_strategy = EXCLUDED.prompt_strategy,
                 model           = EXCLUDED.model,
                 prompt_version  = EXCLUDED.prompt_version,
                 config_path     = EXCLUDED.config_path""",
            (cfg["variant_id"], cfg["prompt_strategy"], cfg["model_name"],
             str(cfg["prompt_version"]), f"configs/variants/{path.name}"),
        )
        n += 1
    return n


def load_questions(cur) -> tuple[int, int]:
    rows = json.loads(QUESTIONS.read_text())
    placeholders = ", ".join(["%s"] * len(Q_COLS))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in Q_COLS if c != "question_id")
    sql = (f"INSERT INTO questions ({', '.join(Q_COLS)}) VALUES ({placeholders}) "
           f"ON CONFLICT (question_id) DO UPDATE SET {updates}")
    cur.executemany(sql, [[r[c] for c in Q_COLS] for r in rows])
    # Sync: remove any questions no longer in the current validated sample (e.g. ones
    # dropped by hand-review). Safe while runs/executions are empty; a question with
    # dependent runs would be protected by the FK, which is the behaviour we want.
    ids = [r["question_id"] for r in rows]
    cur.execute("DELETE FROM questions WHERE question_id <> ALL(%s)", (ids,))
    return len(rows), cur.rowcount


def main() -> int:
    url = require("DATABASE_URL")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            nv = load_variants(cur)
            nq, ndel = load_questions(cur)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT tier, split, count(*) FROM questions GROUP BY tier, split ORDER BY tier, split")
            grid = cur.fetchall()
            cur.execute("SELECT variant_id, prompt_strategy, model FROM variants ORDER BY variant_id")
            variants = cur.fetchall()
    print(f"Upserted {nv} variants, {nq} questions (removed {ndel} stale).\n")
    print("Variants:")
    for v in variants:
        print(f"  {v[0]}: {v[1]:10s} {v[2]}")
    print("\nQuestions by tier × split:")
    for tier, split, c in grid:
        print(f"  {tier:9s} {split:5s} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
