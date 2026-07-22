"""Phase 1, Steps 2-4 — tier, sample, validate ground truth, split.

Pipeline (spec §6.2, §6.3):
  1. Label every Spider example with a tier via the official hardness function.
  2. Per tier, in a FIXED-SEED shuffle, walk candidates and keep a question only if
       - its gold SQL EXECUTES read-only without error, and
       - it returns a NON-EMPTY result set,
     capping at 3 questions per db_id, until 50 valid questions are collected.
  3. Record gold result hash, row/col counts, and schema DDL.
  4. Assign a train/test split, stratified by tier, with whole databases kept on
     one side (so no db_id spans both splits — matters for routing validity §11.2).

Exclusions (gold errored / timed out / zero rows / db-cap) are counted and logged.
Writes data/questions.json (gitignored). Nothing hits Supabase here — that's the
next step (load_questions.py), so this can be re-run freely.

Run:  python scripts/sample_and_validate.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

from yardstick import comparison, sandbox, spider_data as sd
from yardstick.envtools import load_env
from yardstick.hardness import eval_hardness, DIFFICULTY_TO_TIER

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "questions.json"
EXCLUDE_FILE = REPO / "configs" / "excluded_questions.json"

TIERS = ["simple", "moderate", "complex"]
N_PER_TIER = 50
MAX_PER_DB = 3
TRAIN_FRAC = 0.60


def question_id(rec: dict) -> str:
    h = hashlib.sha1(f"{rec['db_id']}|{rec['question']}|{rec['query']}".encode()).hexdigest()
    return f"q{h[:12]}"


def main() -> int:
    load_env()
    seed = int(os.getenv("RANDOM_SEED", "20260721"))
    rng = random.Random(seed)
    print(f"Seed: {seed}")

    excluded_ids: set[str] = set()
    if EXCLUDE_FILE.exists():
        excluded_ids = {e["question_id"] for e in
                        json.loads(EXCLUDE_FILE.read_text()).get("excluded", [])}
    print(f"Manually excluded (hand-review): {len(excluded_ids)}\n")

    examples = sd.load_examples()

    # Label + dedupe by question_id, bucket by tier.
    by_tier: dict[str, list[dict]] = {t: [] for t in TIERS}
    seen: set[str] = set()
    for rec in examples:
        qid = question_id(rec)
        if qid in seen:
            continue
        seen.add(qid)
        rec["_qid"] = qid
        rec["_difficulty"] = eval_hardness(rec["sql"])
        by_tier[DIFFICULTY_TO_TIER[rec["_difficulty"]]].append(rec)

    ddl_cache: dict[str, str] = {}
    def schema_ddl(db_id: str) -> str:
        if db_id not in ddl_cache:
            ddl_cache[db_id] = sd.extract_schema_ddl(db_id)
        return ddl_cache[db_id]

    kept: list[dict] = []
    stats = {t: Counter() for t in TIERS}
    for tier in TIERS:
        pool = by_tier[tier][:]
        rng.shuffle(pool)
        per_db: Counter = Counter()
        n_valid = 0
        for rec in pool:
            if n_valid >= N_PER_TIER:
                break
            if rec["_qid"] in excluded_ids:
                stats[tier]["excluded_manual"] += 1
                continue
            db_id = rec["db_id"]
            if per_db[db_id] >= MAX_PER_DB:
                stats[tier]["skipped_db_cap"] += 1
                continue
            db_path = sd.db_sqlite_path(db_id)
            if not db_path.exists():
                stats[tier]["missing_db"] += 1
                continue
            res = sandbox.execute(db_path, rec["query"])
            if res.timed_out:
                stats[tier]["gold_timeout"] += 1
                continue
            if not res.executed:
                stats[tier]["gold_error"] += 1
                continue
            if res.row_count == 0:
                stats[tier]["gold_zero_rows"] += 1
                continue
            # keep it
            per_db[db_id] += 1
            n_valid += 1
            stats[tier]["kept"] += 1
            kept.append({
                "question_id": rec["_qid"],
                "db_id": db_id,
                "question_text": rec["question"],
                "gold_sql": rec["query"],
                "gold_result_hash": comparison.result_hash(res.rows, order_sensitive=False),
                "gold_row_count": res.row_count,
                "gold_col_count": res.col_count,
                "spider_difficulty": rec["_difficulty"],
                "tier": tier,
                "schema_ddl": schema_ddl(db_id),
                "spider_origin": rec["spider_origin"],
            })
        if n_valid < N_PER_TIER:
            print(f"⚠ tier {tier}: only {n_valid}/{N_PER_TIER} valid questions found!")

    # Train/test split at the db_id level GLOBALLY, so a whole database stays on one
    # side (no db_id spans both splits — required for clean leave-one-database-out and
    # to avoid schema leakage across the split). Target 60% of questions in train.
    split_of: dict[str, str] = {}
    db_to_qs: dict[str, list[dict]] = defaultdict(list)
    for q in kept:
        db_to_qs[q["db_id"]].append(q)
    db_ids = list(db_to_qs)
    rng.shuffle(db_ids)
    target_train = round(len(kept) * TRAIN_FRAC)
    n_train = 0
    for db in db_ids:
        split = "train" if n_train < target_train else "test"
        for q in db_to_qs[db]:
            split_of[q["question_id"]] = split
        if split == "train":
            n_train += len(db_to_qs[db])
    for q in kept:
        q["split"] = split_of[q["question_id"]]

    OUT.write_text(json.dumps(kept, indent=2))

    # Report
    print("Per-tier outcomes:")
    for tier in TIERS:
        s = stats[tier]
        print(f"  {tier:9s} kept={s['kept']:2d}  excluded: "
              f"zero_rows={s['gold_zero_rows']} gold_error={s['gold_error']} "
              f"timeout={s['gold_timeout']} db_cap={s['skipped_db_cap']} "
              f"missing_db={s['missing_db']} hand_review={s['excluded_manual']}")
    print(f"\nTotal kept: {len(kept)}")
    print("Split (overall):", dict(Counter(q["split"] for q in kept)))
    print("Split per tier:")
    for tier in TIERS:
        c = Counter(q["split"] for q in kept if q["tier"] == tier)
        print(f"  {tier:9s} train={c['train']:2d} test={c['test']:2d}")
    print("Distinct dbs:", len({q["db_id"] for q in kept}))
    # sanity: no db spans both splits
    db_splits = defaultdict(set)
    for q in kept:
        db_splits[q["db_id"]].add(q["split"])
    spanning = [db for db, s in db_splits.items() if len(s) > 1]
    print("DBs spanning both splits (should be 0):", len(spanning))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
