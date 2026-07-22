"""Result-set canonicalization and matching (spec §9.2).

Comparison rules, documented in the README:
  - Column order : IGNORED — values are sorted within each row
  - Column names : IGNORED — we compare values, not headers
  - Duplicate rows: PRESERVED — multiset comparison, not set
  - Numeric      : floats rounded to 4 dp before comparison
  - NULL         : treated as a single canonical token, NULL == NULL
  - Row order    : set_match ignores it; exact_match respects it

Two verdicts per pair:
  - set_match   (order-insensitive)  -> THE primary correctness flag
  - exact_match (order-sensitive)
"""
from __future__ import annotations

import hashlib
import json

FLOAT_DP = 4


def _cell_token(v) -> str:
    """A canonical, type-tagged string for one cell, so mixed types sort/compare safely."""
    if v is None:
        return "\x00NULL"
    if isinstance(v, bool):            # bool before int (bool is a subclass of int)
        return f"B:{int(v)}"
    if isinstance(v, float):
        return f"F:{round(v, FLOAT_DP)!r}"
    if isinstance(v, int):
        return f"I:{v}"
    if isinstance(v, (bytes, bytearray)):
        return "X:" + bytes(v).hex()
    return f"S:{v}"


def _canon_row(row) -> tuple[str, ...]:
    # column-order-insensitive: sort the value tokens within the row
    return tuple(sorted(_cell_token(c) for c in row))


def canonical_form(rows, order_sensitive: bool = False) -> list[tuple[str, ...]]:
    canon = [_canon_row(r) for r in rows]
    return canon if order_sensitive else sorted(canon)


def result_hash(rows, order_sensitive: bool = False) -> str:
    payload = json.dumps(canonical_form(rows, order_sensitive), separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def compare(pred_rows, gold_rows) -> dict:
    """Return set_match / exact_match / hashes for a predicted vs gold result set."""
    return {
        "set_match": canonical_form(pred_rows, False) == canonical_form(gold_rows, False),
        "exact_match": canonical_form(pred_rows, True) == canonical_form(gold_rows, True),
        "pred_hash": result_hash(pred_rows, False),
        "gold_hash": result_hash(gold_rows, False),
    }
