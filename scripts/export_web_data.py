"""Export the run matrix as a static JSON the site loads client side.

Feeds three interactive pieces on the page: the judgement quiz, the run explorer, and
the SQL console. All of them read this one file, so there is no server and no database
dependency once it is built.

Keys are short because this ships over the wire on every page load.

`flagged` uses the same rule as scripts/analyze_calibration.py (practical check): a
question is flagged when the result sets of its executed answers do not all agree
(pairwise agreement < 1). Every answer to a flagged question carries flagged = true.

Run:  python scripts/export_web_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

from collections import defaultdict

import psycopg

from yardstick import calibration as cal
from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "data"

MODEL = {"V1": "8B", "V2": "8B", "V3": "70B", "V4": "70B"}
PROMPT = {"V1": "zero-shot", "V2": "few-shot", "V3": "zero-shot", "V4": "few-shot"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT q.question_id, e.result_hash, r.variant_id, q.tier, q.db_id, q.question_text, q.gold_sql,
                   r.extracted_sql, e.set_match, e.executed, e.error_type,
                   r.self_confidence, q.gold_row_count, e.result_row_count,
                   -- rows rebuilt by rebuild_db.py keep only the token total, with the
                   -- split NULL; without this fallback a re-export would zero them
                   COALESCE(r.input_tokens, r.total_tokens), r.output_tokens,
                   r.cost_usd, r.latency_ms
            FROM runs r
            JOIN questions q  ON q.question_id = r.question_id
            JOIN executions e ON e.run_id = r.run_id
            WHERE r.replicate = 1 AND r.error_message IS NULL
            ORDER BY q.tier, q.db_id, q.question_id, r.variant_id""")
        rows = cur.fetchall()

    hashes = defaultdict(list)
    for qid, rh, _vid, *_rest in rows:
        ex = _rest[6]   # tier, db, question, gold, pred, set_match, executed
        if ex:
            hashes[qid].append(rh)
    flagged_q = {qid for qid, hs in hashes.items() if cal.pairwise_agreement(hs) < 1.0}

    runs = []
    for (qid, rh, vid, tier, db, question, gold, pred, sm, ex, etype, conf,
         grows, prows, itok, otok, cost, lat) in rows:
        correct = bool(sm)
        runs.append({
            "qid": qid,
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
            "flagged": qid in flagged_q,
        })

    payload = {
        "generated": "2026-07",
        "n": len(runs),
        "columns": ["qid", "v", "m", "p", "t", "db", "q", "gold", "sql", "ok", "ran",
                    "silent", "err", "conf", "grows", "prows", "tok", "cost", "ms", "flagged"],
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
