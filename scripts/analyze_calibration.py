"""Phase 9 — calibration and cross-variant agreement (spec §12).

  1. Is self-reported confidence calibrated?  ECE + reliability curve, per variant.
  2. Cross-variant agreement (result-set and AST) — computable WITHOUT the gold answer.
  3. Which signal best predicts correctness?  AUC showdown.
  4. Practical recommendation: flag disagreement -> how many errors caught, at what
     false-alarm rate.
  5. The two counterintuitive checks from §12.4.

Run:  python scripts/analyze_calibration.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
from sklearn.metrics import roc_auc_score

from yardstick import calibration as cal
from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
VARIANTS = ["V1", "V2", "V3", "V4"]


def safe_auc(y, s):
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    keep = ~np.isnan(s)
    y, s = y[keep], s[keep]
    return roc_auc_score(y, s) if len(np.unique(y)) > 1 else float("nan")


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    with psycopg.connect(require("DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.question_id, r.variant_id, q.tier, r.self_confidence,
                   r.extracted_sql, e.set_match, e.executed, e.result_hash
            FROM runs r JOIN questions q ON q.question_id=r.question_id
            JOIN executions e ON e.run_id=r.run_id
            WHERE r.replicate=1 AND r.error_message IS NULL""")
        rows = cur.fetchall()

    per_q = defaultdict(dict)
    for qid, vid, tier, conf, sql, sm, ex, rh in rows:
        per_q[qid][vid] = {"tier": tier, "conf": float(conf) if conf is not None else np.nan,
                           "sql": sql, "correct": int(bool(sm)), "executed": bool(ex),
                           "hash": rh}

    # ---------- 1. calibration ----------
    print("1) CALIBRATION of self-reported confidence (§12.2)\n")
    print(f"  {'variant':8} {'n':>4} {'ECE':>7} {'mean conf':>10} {'accuracy':>9}  interpretation")
    calib_rows = []
    for vid in VARIANTS:
        confs = [d[vid]["conf"] for d in per_q.values() if vid in d]
        accs = [d[vid]["correct"] for d in per_q.values() if vid in d]
        if not confs:
            continue
        e, bins = cal.ece(confs, accs)
        mc, ma = np.nanmean(confs), np.mean(accs)
        note = "OVERconfident" if mc > ma + 0.02 else ("underconfident" if mc < ma - 0.02 else "well calibrated")
        print(f"  {vid:8} {len(confs):4d} {e:7.3f} {mc:10.3f} {ma:9.3f}  {note} (says {mc:.0%}, is {ma:.0%})")
        for lo, hi, n, c, a in bins:
            calib_rows.append([vid, round(lo, 2), round(hi, 2), n,
                               None if np.isnan(c) else round(c, 3),
                               None if np.isnan(a) else round(a, 3)])
    with (RESULTS / "calibration.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "bin_low", "bin_high", "n", "mean_confidence", "observed_accuracy"])
        w.writerows(calib_rows)
    print(f"\n  wrote results/calibration.csv (reliability curve data)\n")

    # ---------- 2. agreement ----------
    qids = sorted(per_q)
    res_agree, ast_agree = {}, {}
    for qid in qids:
        d = per_q[qid]
        res_agree[qid] = cal.pairwise_agreement(
            [d[v]["hash"] for v in VARIANTS if v in d and d[v]["executed"]])
        ast_agree[qid] = cal.pairwise_agreement(
            [cal.canonical_sql(d[v]["sql"]) for v in VARIANTS if v in d])
    n_var = [len([v for v in VARIANTS if v in per_q[q]]) for q in qids]
    print(f"2) CROSS-VARIANT AGREEMENT (§12.3) — {np.mean(n_var):.1f} variants/question on average")
    print(f"   mean result-set agreement: {np.nanmean(list(res_agree.values())):.3f}")
    print(f"   mean AST agreement:        {np.nanmean(list(ast_agree.values())):.3f}\n")

    # ---------- 3. AUC showdown ----------
    y, s_conf, s_res, s_ast = [], [], [], []
    for qid in qids:
        for vid in VARIANTS:
            if vid not in per_q[qid]:
                continue
            y.append(per_q[qid][vid]["correct"])
            s_conf.append(per_q[qid][vid]["conf"])
            s_res.append(res_agree[qid])
            s_ast.append(ast_agree[qid])
    print("3) WHICH SIGNAL PREDICTS CORRECTNESS? (AUC for predicting set_match; 0.5 = useless)")
    print(f"   self-reported confidence : {safe_auc(y, s_conf):.3f}")
    print(f"   result-set agreement     : {safe_auc(y, s_res):.3f}")
    print(f"   AST agreement            : {safe_auc(y, s_ast):.3f}\n")

    # ---------- 4. practical recommendation ----------
    print("4) PRACTICAL: flag for human review when variants DISAGREE (no gold needed)")
    y_arr = np.array(y)
    for label, sig in [("result-set", np.array(s_res, dtype=float)),
                       ("AST", np.array(s_ast, dtype=float))]:
        flagged = np.nan_to_num(sig, nan=1.0) < 1.0     # any disagreement at all
        st = cal.flag_stats(flagged, y_arr)
        print(f"   {label:11s} disagreement: flags {st['flag_rate']:.0%} of outputs, "
              f"catches {st['recall']:.0%} of errors, false alarms {st['false_alarm_rate']:.0%}")
    print()

    # ---------- 5. counterintuitive checks (§12.4) ----------
    print("5) COUNTERINTUITIVE CHECKS (§12.4)")
    print("   (a) mean stated confidence ON ERRORS — is the better model more overconfident?")
    for vid in VARIANTS:
        errs = [d[vid]["conf"] for d in per_q.values()
                if vid in d and not d[vid]["correct"]]
        acc = np.mean([d[vid]["correct"] for d in per_q.values() if vid in d]) if any(
            vid in d for d in per_q.values()) else float("nan")
        if errs:
            print(f"       {vid}: acc={acc:.2f}  mean confidence when WRONG={np.nanmean(errs):.3f} "
                  f"(n={len(errs)})")
    print("   (b) share of ERRORS that are SILENT (executed cleanly but wrong)")
    for vid in VARIANTS:
        recs = [d[vid] for d in per_q.values() if vid in d]
        errs = [r for r in recs if not r["correct"]]
        if errs:
            silent = sum(1 for r in errs if r["executed"])
            print(f"       {vid}: {silent}/{len(errs)} of errors are silent "
                  f"({silent/len(errs):.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
