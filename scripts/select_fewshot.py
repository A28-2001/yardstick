"""Phase 2, pick held-out few-shot examples and write configs/fewshot_examples.yaml.

Hard constraints:
  - db_id must NOT appear in the 150-question sample (no leakage, §4.5/§11.3)
  - gold query must execute read-only and return a non-empty result
  - prefer SMALL schemas (few-shot goes in every V2/V4 prompt; keep token cost low)
One example per difficulty (easy/medium/hard) to demonstrate the range.
Deterministic (fixed seed). Result is committed for reproducibility.

Run:  python scripts/select_fewshot.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from yardstick import sandbox, spider_data as sd
from yardstick.envtools import load_env
from yardstick.hardness import eval_hardness

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "data" / "questions.json"
OUT = REPO / "configs" / "fewshot_examples.yaml"

WANT = [("easy", 0.95), ("medium", 0.9), ("hard", 0.85)]
MAX_SCHEMA_CHARS = 700
MAX_SQL_CHARS = 200


def main() -> int:
    load_env()
    seed = int(os.getenv("RANDOM_SEED", "20260721"))

    sample_dbs = {q["db_id"] for q in json.loads(SAMPLE.read_text())}
    examples = sd.load_examples()

    # Deterministic order independent of file order.
    examples.sort(key=lambda e: f"{e['db_id']}|{e['question']}")

    ddl_cache: dict[str, str] = {}
    def ddl(db_id: str) -> str:
        if db_id not in ddl_cache:
            ddl_cache[db_id] = sd.extract_schema_ddl(db_id)
        return ddl_cache[db_id]

    chosen: list[dict] = []
    for difficulty, conf in WANT:
        pick = None
        for e in examples:
            if e["db_id"] in sample_dbs:
                continue
            if eval_hardness(e["sql"]) != difficulty:
                continue
            if len(e["query"]) > MAX_SQL_CHARS:
                continue
            schema = ddl(e["db_id"])
            if len(schema) > MAX_SCHEMA_CHARS:
                continue
            res = sandbox.execute(sd.db_sqlite_path(e["db_id"]), e["query"])
            if not res.executed or res.row_count == 0:
                continue
            pick = {"difficulty": difficulty, "db_id": e["db_id"],
                    "schema_ddl": schema, "question": e["question"],
                    "sql": " ".join(e["query"].split()), "confidence": conf}
            break
        if pick is None:
            print(f"⚠ no held-out example found for difficulty={difficulty}")
            continue
        # keep chosen db_ids distinct from each other too
        sample_dbs.add(pick["db_id"])
        chosen.append(pick)

    OUT.write_text(yaml.safe_dump({"examples": chosen}, sort_keys=False, width=1000))
    print(f"Wrote {len(chosen)} few-shot examples to {OUT}\n")
    for c in chosen:
        print(f"  [{c['difficulty']:6s}] db={c['db_id']} schema={len(c['schema_ddl'])}ch")
        print(f"           Q: {c['question']}")
        print(f"           SQL: {c['sql']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
