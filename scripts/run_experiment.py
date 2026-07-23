"""Phase 2 — generation run loop (spec §8.1).

For each (question, variant, replicate) cell: if a run already exists it is SKIPPED
(cache/resume — costs zero), otherwise we build the prompt, call Groq, extract the
SQL + confidence, and write the run to Postgres IMMEDIATELY (never batched, so a
rate-limit interruption never loses progress).

CACHE SEMANTICS: the resume key is (question_id, variant_id, replicate). It does NOT
re-hash the prompt text, so if you EDIT a variant's prompt or bump its temperature,
existing runs won't auto-invalidate — re-run that variant with --force to regenerate.
(Bump prompt_version in the config too, so the change is recorded.)

Filters let you run a slice (one variant, one tier, a few questions) — used for the
pilot and the single-tier run before the full sweep.

Examples:
  python scripts/run_experiment.py --variant V1 --limit 1          # smoke test
  python scripts/run_experiment.py --variant all --tier moderate   # one tier, all variants
  python scripts/run_experiment.py --variant all                   # everything (resumable)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
import yaml

from yardstick import clients, extraction, prompting
from yardstick.envtools import first_line, require

REPO = Path(__file__).resolve().parents[1]
VARIANT_DIR = REPO / "configs" / "variants"
PILOT_FILE = REPO / "configs" / "pilot_questions.json"


def load_variants() -> dict[str, dict]:
    out = {}
    for path in VARIANT_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(path.read_text())
        out[cfg["variant_id"]] = cfg
    return out


def fetch_questions(cur, tier=None, split=None, limit=None, pilot=False) -> list[dict]:
    q = ("SELECT question_id, question_text, schema_ddl, tier, split, gold_sql, db_id "
         "FROM questions")
    conds, args = [], []
    if pilot:
        ids = json.loads(PILOT_FILE.read_text())["question_ids"]
        conds.append("question_id = ANY(%s)"); args.append(ids)
    if tier:
        conds.append("tier = %s"); args.append(tier)
    if split:
        conds.append("split = %s"); args.append(split)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY tier, question_id"
    if limit:
        q += f" LIMIT {int(limit)}"
    cur.execute(q, args)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run_exists(cur, qid, vid, replicate) -> bool:
    # A cell counts as done only if the API call SUCCEEDED (error_message IS NULL).
    # Generation failures (e.g. hitting the daily token cap) are retried on resume,
    # not skipped — important for the multi-day full run.
    cur.execute("SELECT 1 FROM runs WHERE question_id=%s AND variant_id=%s AND replicate=%s "
                "AND error_message IS NULL", (qid, vid, replicate))
    return cur.fetchone() is not None


def write_run(cur, qid, vid, replicate, cfg, comp: clients.Completion | None,
              ext: extraction.Extraction | None, error: str | None):
    raw = comp.text if comp else (error or "")
    cur.execute(
        """INSERT INTO runs (question_id, variant_id, replicate, raw_output, extracted_sql,
             extraction_success, self_confidence, input_tokens, output_tokens, cost_usd,
             latency_ms, temperature, error_message)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (question_id, variant_id, replicate) DO UPDATE SET
             raw_output=EXCLUDED.raw_output, extracted_sql=EXCLUDED.extracted_sql,
             extraction_success=EXCLUDED.extraction_success, self_confidence=EXCLUDED.self_confidence,
             input_tokens=EXCLUDED.input_tokens, output_tokens=EXCLUDED.output_tokens,
             cost_usd=EXCLUDED.cost_usd, latency_ms=EXCLUDED.latency_ms,
             temperature=EXCLUDED.temperature, error_message=EXCLUDED.error_message""",
        (qid, vid, replicate, raw,
         ext.sql if ext else None,
         bool(ext and ext.extraction_success),
         ext.confidence if ext else None,
         comp.input_tokens if comp else 0,
         comp.output_tokens if comp else 0,
         comp.cost_usd if comp else 0.0,
         comp.latency_ms if comp else 0,
         cfg["temperature"], error),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all", help="V1|V2|V3|V4|all")
    ap.add_argument("--tier", choices=["simple", "moderate", "complex"])
    ap.add_argument("--split", choices=["train", "test"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--pilot", action="store_true", help="restrict to the fixed pilot set")
    ap.add_argument("--replicate", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="ignore cache, regenerate")
    args = ap.parse_args()

    variants = load_variants()
    vids = list(variants) if args.variant == "all" else [args.variant]
    vids.sort()

    done = skipped = failed = 0
    with psycopg.connect(require("DATABASE_URL")) as conn:
        with conn.cursor() as cur:
            questions = fetch_questions(cur, args.tier, args.split, args.limit, args.pilot)
        print(f"{len(questions)} questions × {len(vids)} variants "
              f"× replicate {args.replicate} = {len(questions)*len(vids)} cells\n")
        for vid in vids:
            cfg = variants[vid]
            for q in questions:
                with conn.cursor() as cur:
                    if not args.force and run_exists(cur, q["question_id"], vid, args.replicate):
                        skipped += 1
                        continue
                    try:
                        msgs = prompting.build_messages(cfg, q)
                        comp = clients.generate(cfg["model_name"], msgs,
                                                temperature=cfg["temperature"],
                                                max_tokens=cfg["max_tokens"])
                        ext = extraction.extract(comp.text)
                        write_run(cur, q["question_id"], vid, args.replicate, cfg, comp, ext, None)
                        done += 1
                        tag = "ok" if ext.extraction_success else "NO-SQL"
                        print(f"  {vid} {q['question_id']} [{q['tier']:8s}] "
                              f"{comp.input_tokens}+{comp.output_tokens}tok "
                              f"${comp.cost_usd:.5f} conf={ext.confidence} {tag}")
                    except Exception as e:  # noqa: BLE001
                        write_run(cur, q["question_id"], vid, args.replicate, cfg, None, None, str(e))
                        failed += 1
                        print(f"  {vid} {q['question_id']} FAILED: {first_line(e)}")
                conn.commit()  # persist after every call

    print(f"\nGenerated {done}, skipped(cached) {skipped}, failed {failed}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
