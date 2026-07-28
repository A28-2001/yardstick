"""Export the run matrix as a static JSON the site loads client side.

Feeds three interactive pieces on the page: the judgement quiz, the run explorer, and
the SQL console. All of them read this one file, so there is no server and no database
dependency once it is built.

Keys are short because this ships over the wire on every page load.

Run:  python scripts/export_web_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "data"

MODEL = {"V1": "8B", "V2": "8B", "V3": "70B", "V4": "70B"}
PROMPT = {"V1": "zero-shot", "V2": "few-shot", "V3": "zero-shot", "V4": "few-shot"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.variant_id, q.tier, q.db_id, q.question_text, q.gold_sql,
                   r.extracted_sql, e.set_match, e.executed, e.error_type,
                   r.self_confidence, q.gold_row_count, e.result_row_count,
                   r.input_tokens, r.output_tokens, r.cost_usd, r.latency_ms
            FROM runs r
            JOIN questions q  ON q.question_id = r.question_id
            JOIN executions e ON e.run_id = r.run_id
            WHERE r.replicate = 1 AND r.error_message IS NULL
            ORDER BY q.tier, q.db_id, r.variant_id""")
        rows = cur.fetchall()

    runs = []
    for (vid, tier, db, question, gold, pred, sm, ex, etype, conf,
         grows, prows, itok, otok, cost, lat) in rows:
        correct = bool(sm)
        runs.append({
            "v": vid,
            "m": MODEL[vid],
            "p": PROMPT[vid],
            "t": tier,
            "db": db,
            "q": question,
            "gold": " ".join((gold or "").split()),
            "sql": " ".join((pred or "").split()),
            "ok": correct,
            "ran": bool(ex),
            # silent: it executed without complaint and still returned the wrong rows
            "silent": bool(ex) and not correct,
            "err": etype,
            "conf": float(conf) if conf is not None else None,
            "grows": grows,
            "prows": prows,
            "tok": (itok or 0) + (otok or 0),
            "cost": round(float(cost or 0), 6),
            "ms": lat,
        })

    payload = {
        "generated": "2026-07",
        "n": len(runs),
        "columns": ["v", "m", "p", "t", "db", "q", "gold", "sql", "ok", "ran",
                    "silent", "err", "conf", "grows", "prows", "tok", "cost", "ms"],
        "runs": runs,
    }
    path = OUT / "runs.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    kb = path.stat().st_size / 1024

    print(f"wrote {path.relative_to(REPO)}  {len(runs)} runs  {kb:.0f} KB")
    print(f"  correct {sum(r['ok'] for r in runs)}  "
          f"silent {sum(r['silent'] for r in runs)}  "
          f"loud {sum(1 for r in runs if not r['ok'] and not r['ran'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
