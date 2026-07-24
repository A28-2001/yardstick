"""Phase 7 — exploratory analyses (spec §10.4: reported WITHOUT correction, labelled exploratory).

  - Model effect:  V3 vs V1 (70B vs 8B, zero-shot) and V4 vs V2 (few-shot), McNemar + CI.
  - Prompt effect on the strong model: V4 vs V3.
  - 2x2 interaction: does few-shot help the strong model more than the cheap one?
    DiD = (V4-V3) - (V2-V1) with a bootstrap CI.
  - Query efficiency (§9.6): median execution time of CORRECT queries per variant per tier
    (SQLite time on tiny benchmark DBs is a weak warehouse proxy — stated as such).

Uses replicate 1, valid generations only (error_message IS NULL). Robust to an
incomplete matrix: pairs on questions where the needed variants are all present and
reports n (flags < 50). Run:  python scripts/analyze_exploratory.py [--tier complex]
"""
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict

import psycopg

from yardstick import stats
from yardstick.envtools import require

TIERS = ["simple", "moderate", "complex"]


def load(cur, tier=None):
    q = ("""SELECT q.tier, r.variant_id, r.question_id, e.set_match, e.execution_time_ms
            FROM runs r JOIN questions q ON q.question_id=r.question_id
            JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL""")
    params = []
    if tier:
        q += " AND q.tier=%s"; params.append(tier)
    cur.execute(q, params)
    sm = defaultdict(lambda: defaultdict(dict))   # tier->qid->variant->set_match
    et = defaultdict(lambda: defaultdict(dict))   # tier->qid->variant->exec_time (correct only)
    for t, v, qid, s, ems in cur.fetchall():
        sm[t][qid][v] = int(bool(s))
        if s and ems is not None:
            et[t][qid][v] = float(ems)
    return sm, et


def paired(sm, tier, va, vb):
    qs = [q for q in sm[tier] if va in sm[tier][q] and vb in sm[tier][q]]
    return [sm[tier][q][va] for q in qs], [sm[tier][q][vb] for q in qs]


def show(name, sm, tier, va, vb):
    a, b = paired(sm, tier, va, vb)
    if not a:
        print(f"    {name}: no paired data"); return
    r = stats.compare_paired(a, b)
    flag = "" if r.n == 50 else f"  ⚠ n={r.n}<50 (incomplete)"
    print(f"    {name}: {va}={r.acc_a:.2f} -> {vb}={r.acc_b:.2f}  "
          f"diff={r.diff_pts:+.0f}pts CI[{r.ci_low_pts:+.0f},{r.ci_high_pts:+.0f}]  "
          f"McNemar p={r.p_value:.4f}  (n={r.n}){flag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=TIERS)
    args = ap.parse_args()

    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        sm, et = load(cur, args.tier)
    tiers = [t for t in TIERS if t in sm]

    print("EXPLORATORY (uncorrected, per pre-registration §10.4)\n")
    for tier in tiers:
        print(f"[{tier}]")
        show("model effect, zero-shot (V3 vs V1)", sm, tier, "V1", "V3")
        show("model effect, few-shot  (V4 vs V2)", sm, tier, "V2", "V4")
        show("prompt effect on 70B    (V4 vs V3)", sm, tier, "V3", "V4")

        # interaction (needs all 4 on the same questions)
        qs = [q for q in sm[tier] if all(v in sm[tier][q] for v in ("V1", "V2", "V3", "V4"))]
        if qs:
            v = {k: [sm[tier][q][k] for q in qs] for k in ("V1", "V2", "V3", "V4")}
            pt, lo, hi = stats.diff_in_diff(v["V1"], v["V2"], v["V3"], v["V4"])
            flag = "" if len(qs) == 50 else f"  ⚠ n={len(qs)}<50 (incomplete)"
            sig = "excludes 0" if (lo > 0 or hi < 0) else "includes 0"
            print(f"    interaction DiD (V4-V3)-(V2-V1) = {pt:+.0f}pts  "
                  f"CI[{lo:+.0f},{hi:+.0f}] ({sig})  (n={len(qs)}){flag}")
        else:
            print("    interaction: not all 4 variants present yet")

        # query efficiency (correct queries only)
        effs = []
        for vv in ("V1", "V2", "V3", "V4"):
            times = [et[tier][q][vv] for q in et[tier] if vv in et[tier][q]]
            effs.append(f"{vv}={statistics.median(times):.1f}ms(n{len(times)})" if times else f"{vv}=-")
        print("    median exec time, correct queries: " + "  ".join(effs))
        print()
    print("(SQLite on small benchmark DBs is a weak warehouse-performance proxy — §9.6.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
