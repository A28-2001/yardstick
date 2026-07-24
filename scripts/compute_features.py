"""Phase 8 — compute question/schema features and populate question_features (spec §11.3).

Reads ONLY question_text and schema_ddl from the questions table (never gold_sql — see
the leakage warning in yardstick/features.py) and upserts the 15 features per question.

Run:  python scripts/compute_features.py
"""
from __future__ import annotations

import psycopg

from yardstick.envtools import require
from yardstick.features import FEATURE_NAMES, all_features


def main() -> int:
    cols = ["question_id"] + FEATURE_NAMES
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in FEATURE_NAMES)
    sql = (f"INSERT INTO question_features ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT (question_id) DO UPDATE SET {updates}")

    with psycopg.connect(require("DATABASE_URL")) as conn:
        with conn.cursor() as cur:
            # NOTE: gold_sql is deliberately NOT selected — it must never reach a feature.
            cur.execute("SELECT question_id, question_text, schema_ddl FROM questions")
            rows = cur.fetchall()
            payload = []
            for qid, qtext, ddl in rows:
                f = all_features(qtext, ddl)
                payload.append([qid] + [f[k] for k in FEATURE_NAMES])
            cur.executemany(sql, payload)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM question_features")
            n = cur.fetchone()[0]
            cur.execute("""SELECT q.tier,
                                  round(avg(f.question_token_count)) qtok,
                                  round(avg(f.schema_table_count)) tables,
                                  round(avg(f.schema_column_count)) cols,
                                  round(avg(f.foreign_key_count)) fks,
                                  round(avg(f.clause_count)) clauses
                           FROM question_features f JOIN questions q USING (question_id)
                           GROUP BY q.tier ORDER BY q.tier""")
            stats = cur.fetchall()

    print(f"Populated question_features for {n} questions.\n")
    print("Mean feature values by tier (sanity check — harder tiers should look 'bigger'):")
    print(f"  {'tier':9} {'q_tokens':>9} {'tables':>7} {'columns':>8} {'fks':>5} {'clauses':>8}")
    for tier, qtok, tables, cols_, fks, clauses in stats:
        print(f"  {tier:9} {qtok:9} {tables:7} {cols_:8} {fks:5} {clauses:8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
