"""Phase 4, pick the fixed 10-question pilot set (spec §14, Phase 4).

Stratified across tiers (4 simple / 3 moderate / 3 complex = 10). Deterministic:
takes the first K per tier by question_id, which is effectively a random pick since
question_id is a content hash, and it maximizes reuse of the V1 predictions already
generated in Phase 3 (same first-per-tier ordering). Result is committed
(configs/pilot_questions.json) so the pilot set is fixed and reproducible before the
pre-registration.

Run:  python scripts/select_pilot.py
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "configs" / "pilot_questions.json"
PER_TIER = {"simple": 4, "moderate": 3, "complex": 3}


def main() -> int:
    picks = []
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        for tier, k in PER_TIER.items():
            cur.execute(
                "SELECT question_id FROM questions WHERE tier=%s ORDER BY question_id LIMIT %s",
                (tier, k))
            for (qid,) in cur.fetchall():
                picks.append({"question_id": qid, "tier": tier})

    OUT.write_text(json.dumps(
        {"_comment": "Fixed pilot set (spec §14 Phase 4): 4 simple / 3 moderate / 3 complex, "
                     "first-per-tier by question_id. Committed before pre-registration.",
         "question_ids": [p["question_id"] for p in picks],
         "detail": picks}, indent=2))
    print(f"Wrote {len(picks)} pilot questions to {OUT}")
    for p in picks:
        print(f"  {p['tier']:9s} {p['question_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
