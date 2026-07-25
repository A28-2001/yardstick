"""Phase 8, train and validate the difficulty predictor (spec §11.2, §11.4, §11.5).

Target: "hard" = the CHEAP model (V1) got the question wrong, i.e. questions that
should be routed up to the strong model. Features are question+schema only (no gold SQL).

Reports:
  1. Held-out test performance vs the three mandatory baselines
     (length-only, schema-size-only, random), §11.4.
  2. Leave-one-TIER-out generalisation, §11.2.
  3. Leave-one-DATABASE-out generalisation (pooled out-of-fold AUC), the real
     production question: does it transfer to schemas never seen?, §11.2.
  4. Does it recover Spider's HUMAN difficulty label? (accuracy + confusion matrix), §11.5.

Run:  python scripts/train_router.py
"""
from __future__ import annotations

import numpy as np
import psycopg
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from yardstick import routing
from yardstick.envtools import require

TIERS = ["simple", "moderate", "complex"]
SEED = 20260721


def safe_auc(y, p):
    return roc_auc_score(y, p) if len(np.unique(y)) > 1 else float("nan")


def main() -> int:
    with psycopg.connect(require("DATABASE_URL")) as conn:
        df = routing.load_routing_data(conn)

    print(f"Routing dataset: {len(df)} questions with complete cheap/strong counterfactuals")
    print(f"  base rate of 'hard' (cheap model failed): {df['is_hard'].mean():.2f}\n")

    train, test = df[df.split == "train"], df[df.split == "test"]
    print(f"1) HELD-OUT TEST (train n={len(train)}, test n={len(test)}). AUC for predicting 'hard'")
    rng = np.random.default_rng(SEED)
    contenders = {
        "difficulty model (6 feat)": routing.ROUTER_FEATURES,
        "baseline: length only": routing.LENGTH_ONLY,
        "baseline: schema size only": routing.SCHEMA_ONLY,
    }
    for name, feats in contenders.items():
        p = routing.fit_predict_proba(train, test, feats)
        print(f"   {name:28s} AUC={safe_auc(test['is_hard'], p):.3f}")
    print(f"   {'baseline: random':28s} AUC={safe_auc(test['is_hard'], rng.random(len(test))):.3f}\n")

    print("2) LEAVE-ONE-TIER-OUT (train on 2 tiers, test on the held-out tier)")
    for tier in TIERS:
        tr, te = df[df.tier != tier], df[df.tier == tier]
        if te.empty:
            continue
        p = routing.fit_predict_proba(tr, te, routing.ROUTER_FEATURES)
        print(f"   held-out {tier:9s} n={len(te):3d}  AUC={safe_auc(te['is_hard'], p):.3f}")
    print()

    print("3) LEAVE-ONE-DATABASE-OUT (pooled out-of-fold AUC, transfers to unseen schemas?)")
    logo = LeaveOneGroupOut()
    oof = np.full(len(df), np.nan)
    X = df[routing.ROUTER_FEATURES].to_numpy(dtype=float)
    for tr_idx, te_idx in logo.split(X, df["is_hard"], groups=df["db_id"]):
        p = routing.fit_predict_proba(df.iloc[tr_idx], df.iloc[te_idx], routing.ROUTER_FEATURES)
        oof[te_idx] = p
    print(f"   {df['db_id'].nunique()} databases / folds   pooled AUC={safe_auc(df['is_hard'], oof):.3f}\n")

    print("4) DOES IT RECOVER SPIDER'S HUMAN DIFFICULTY LABEL? (§11.5)")
    y_tier = df["tier"].to_numpy()
    m = Pipeline([("scale", StandardScaler()),
                  ("lr", LogisticRegression(max_iter=1000))])
    tr_mask = (df.split == "train").to_numpy()
    m.fit(X[tr_mask], y_tier[tr_mask])
    pred = m.predict(X[~tr_mask])
    acc = accuracy_score(y_tier[~tr_mask], pred)
    print(f"   3-class tier prediction accuracy on test: {acc:.3f} (chance ≈ 0.33)")
    cm = confusion_matrix(y_tier[~tr_mask], pred, labels=TIERS)
    print(f"   confusion matrix (rows=true, cols=pred; order {TIERS}):")
    for lbl, row in zip(TIERS, cm):
        print(f"     {lbl:9s} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
