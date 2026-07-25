"""Difficulty prediction + routing simulation (spec §11).

Routing decision: for each question, send it to the CHEAP model (V1, Llama-8B) or the
STRONG model (V3, Llama-70B), both zero-shot, so the only thing that varies is model
cost/capability. Because every variant ran on every question, the counterfactual matrix
is complete and simulating any policy costs ZERO extra API calls (§11.1).

The predictor uses ONLY question+schema features (yardstick/features.py), never gold
SQL, so the routing decision is available before generating anything.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CHEAP, STRONG = "V1", "V3"

# Spec §11.4: 4-6 features max at n=150 (more would overfit). Fixed a priori, not
# selected on the data, to avoid selection bias.
ROUTER_FEATURES = [
    "question_token_count",   # length proxy
    "schema_table_count",     # search-space size
    "schema_column_count",    # search-space size
    "foreign_key_count",      # join-complexity potential
    "clause_count",           # compound conditions
    "has_aggregation_cue",    # implies GROUP BY
]
LENGTH_ONLY = ["question_token_count"]
SCHEMA_ONLY = ["schema_table_count"]

_FEATURE_COLS = sorted(set(ROUTER_FEATURES + LENGTH_ONLY + SCHEMA_ONLY))


def load_routing_data(conn) -> pd.DataFrame:
    """One row per question: features + cheap/strong correctness and cost."""
    feat_sel = ", ".join(f"f.{c}" for c in _FEATURE_COLS)
    sql = f"""
        SELECT q.question_id, q.tier, q.split, q.db_id, q.spider_difficulty, {feat_sel},
               MAX(CASE WHEN r.variant_id='{CHEAP}'  THEN e.set_match::int END) AS cheap_correct,
               MAX(CASE WHEN r.variant_id='{STRONG}' THEN e.set_match::int END) AS strong_correct,
               MAX(CASE WHEN r.variant_id='{CHEAP}'  THEN r.cost_usd END)       AS cheap_cost,
               MAX(CASE WHEN r.variant_id='{STRONG}' THEN r.cost_usd END)       AS strong_cost
        FROM questions q
        JOIN question_features f ON f.question_id = q.question_id
        JOIN runs r ON r.question_id = q.question_id
                   AND r.replicate = 1 AND r.error_message IS NULL
                   AND r.variant_id IN ('{CHEAP}','{STRONG}')
        JOIN executions e ON e.run_id = r.run_id
        GROUP BY q.question_id, q.tier, q.split, q.db_id, q.spider_difficulty, {feat_sel}
    """
    with conn.cursor() as cur:               # plain DBAPI cursor (pandas.read_sql wants SQLAlchemy)
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    # keep only questions where BOTH variants ran (a complete counterfactual pair)
    df = df.dropna(subset=["cheap_correct", "strong_correct"]).reset_index(drop=True)
    for c in ("cheap_correct", "strong_correct"):
        df[c] = df[c].astype(int)
    for c in ("cheap_cost", "strong_cost"):
        df[c] = df[c].astype(float)
    # TARGET: "hard" = the cheap model got it wrong -> such questions should be routed up.
    df["is_hard"] = 1 - df["cheap_correct"]
    return df


def make_model(features: list[str]) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])


def fit_predict_proba(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Fit on train, return P(hard) for test. Degenerate targets -> constant prediction."""
    y = train["is_hard"].to_numpy()
    if len(np.unique(y)) < 2:
        return np.full(len(test), float(y.mean()))
    m = make_model(features)
    m.fit(train[features].to_numpy(dtype=float), y)
    return m.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
