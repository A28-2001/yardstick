"""Error taxonomy (spec §9.5). Classify each failure into exactly ONE type.

Classification order matters — check in sequence, assign the first match, so each
failure lands in exactly one bucket:

  generation_failure  the API call itself failed (outside the spec's core 9; kept
                      separate from extraction_failure so we don't conflate them)
  extraction_failure  no parseable SQL in the model output
  timeout             execution exceeded the 30s limit
  schema_error        references a nonexistent table/column
  syntax_error        SQL failed to execute for another reason
  --- executed cleanly but wrong (SILENT failures), by first structural diff: ---
  wrong_join          FROM/JOIN tables differ from gold
  wrong_aggregation   GROUP BY / aggregate functions differ
  wrong_filter        WHERE/HAVING predicates differ
  wrong_projection    selected columns differ
  semantically_different  executes, wrong, no single structural diff isolated

Correct answers (set_match=True) get error_type = None.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

_SCHEMA_ERR_MARKERS = ("no such table", "no such column", "no such function")


def _parse(sql: str | None):
    if not sql:
        return None
    try:
        return sqlglot.parse_one(sql, read="sqlite")
    except Exception:  # noqa: BLE001
        return None


def _tables(tree) -> list[str]:
    return sorted(t.name.lower() for t in tree.find_all(exp.Table))


def _agg_signature(tree) -> list[str]:
    aggs = sorted(type(f).__name__.lower() for f in tree.find_all(exp.AggFunc))
    group = tree.find(exp.Group)
    n_group = len(group.expressions) if group else 0
    return aggs + [f"group:{n_group}"]


def _predicates(tree) -> str:
    parts = []
    for clause in (exp.Where, exp.Having):
        node = tree.find(clause)
        parts.append(node.this.sql().lower() if node else "")
    return " || ".join(parts)


def _projection(tree) -> list[str]:
    sel = tree.find(exp.Select)
    if not sel:
        return []
    out = []
    for e in sel.expressions:
        node = e.this if isinstance(e, exp.Alias) else e   # ignore aliases
        out.append(node.sql().lower())
    return sorted(out)


def classify_silent(pred_sql: str | None, gold_sql: str) -> str:
    """Executed cleanly but wrong: find the first structural difference vs gold."""
    pt, gt = _parse(pred_sql), _parse(gold_sql)
    if pt is None or gt is None:
        return "semantically_different"
    if _tables(pt) != _tables(gt):
        return "wrong_join"
    if _agg_signature(pt) != _agg_signature(gt):
        return "wrong_aggregation"
    if _predicates(pt) != _predicates(gt):
        return "wrong_filter"
    if _projection(pt) != _projection(gt):
        return "wrong_projection"
    return "semantically_different"


def classify(*, set_match: bool, extraction_success: bool, generation_error: bool,
             executed: bool, timed_out: bool, execution_error: str | None,
             extracted_sql: str | None, gold_sql: str) -> str | None:
    """Return the single error_type for a run, or None if it is correct."""
    if set_match:
        return None
    if generation_error:
        return "generation_failure"
    if not extraction_success:
        return "extraction_failure"
    if timed_out:
        return "timeout"
    if not executed:
        msg = (execution_error or "").lower()
        if any(m in msg for m in _SCHEMA_ERR_MARKERS):
            return "schema_error"
        return "syntax_error"
    # executed cleanly, wrong result -> a silent failure
    return classify_silent(extracted_sql, gold_sql)
