"""Question + schema features for difficulty prediction (spec §11.3).

=====================================================================================
HARD CONSTRAINT — READ BEFORE ADDING ANY FEATURE (spec §11.3, §17):

    EVERY feature here MUST be computable from the QUESTION TEXT and the SCHEMA DDL
    ALONE, before any SQL is generated, and without an LLM call.

    NO feature may derive from the gold SQL (or from any generated SQL, or from
    execution results). The gold query does not exist at inference time in production,
    so using it would invalidate the entire routing result — this is the single most
    likely way to accidentally break this study.
=====================================================================================
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

# --- question-level regex cues (spec §11.3) ---
_SUPERLATIVE = re.compile(r"\b(most|least|highest|lowest|top|best|worst|maximum|minimum|max|min|largest|smallest)\b", re.I)
_COMPARISON = re.compile(r"\b(more than|less than|at least|at most|greater|fewer|between|above|below|over|under)\b", re.I)
_AGGREGATION = re.compile(r"\b(total|average|avg|sum|count|number of|how many|per|each|mean)\b", re.I)
_TEMPORAL = re.compile(r"\b(date|year|month|day|before|after|since|during|earliest|latest|recent)\b", re.I)
_NEGATION = re.compile(r"\b(not|never|without|excluding|exclude|no longer|don't|doesn't)\b", re.I)
_CLAUSE = re.compile(r"\b(and|or|but|that|which|who|whose|where)\b", re.I)
_NUMERIC = re.compile(r"\b\d+(?:\.\d+)?\b")
_QUOTED = re.compile(r"['\"][^'\"]+['\"]")


def question_features(question: str) -> dict:
    tokens = question.split()
    # entities: quoted strings + capitalised tokens that are not the first word
    capitalised = sum(1 for t in tokens[1:] if t[:1].isupper())
    return {
        "question_token_count": len(tokens),
        "question_char_count": len(question),
        "question_entity_count": len(_QUOTED.findall(question)) + capitalised,
        "has_superlative": bool(_SUPERLATIVE.search(question)),
        "has_comparison": bool(_COMPARISON.search(question)),
        "has_aggregation_cue": bool(_AGGREGATION.search(question)),
        "has_temporal_cue": bool(_TEMPORAL.search(question)),
        "has_negation": bool(_NEGATION.search(question)),
        "clause_count": len(_CLAUSE.findall(question)),
        "numeric_mention_count": len(_NUMERIC.findall(question)),
    }


def schema_features(schema_ddl: str) -> dict:
    """Parse the stored CREATE TABLE DDL. Falls back to regex if sqlglot chokes."""
    table_cols: list[int] = []
    fk_count = 0
    try:
        for stmt in sqlglot.parse(schema_ddl, read="sqlite"):
            if not isinstance(stmt, exp.Create):
                continue
            table_cols.append(len(list(stmt.find_all(exp.ColumnDef))))
            fk_count += len(list(stmt.find_all(exp.ForeignKey)))
    except Exception:  # noqa: BLE001
        table_cols = []
    if not table_cols:  # fallback
        table_cols = [schema_ddl.count(",") + 1] if schema_ddl else [0]
        fk_count = len(re.findall(r"FOREIGN\s+KEY", schema_ddl, re.I))
    return {
        "schema_table_count": len(re.findall(r"CREATE\s+TABLE", schema_ddl, re.I)) or len(table_cols),
        "schema_column_count": sum(table_cols),
        "schema_ddl_token_count": len(schema_ddl.split()),
        "foreign_key_count": fk_count,
        "max_table_column_count": max(table_cols) if table_cols else 0,
    }


def all_features(question: str, schema_ddl: str) -> dict:
    """The full feature vector. Inputs are ONLY the question and the schema DDL."""
    return {**question_features(question), **schema_features(schema_ddl)}


FEATURE_NAMES = [
    "question_token_count", "question_char_count", "question_entity_count",
    "has_superlative", "has_comparison", "has_aggregation_cue", "has_temporal_cue",
    "has_negation", "clause_count", "numeric_mention_count",
    "schema_table_count", "schema_column_count", "schema_ddl_token_count",
    "foreign_key_count", "max_table_column_count",
]
