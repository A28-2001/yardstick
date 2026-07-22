"""Extract SQL (and self-reported confidence) from a model's raw output (spec §8.3).

Extraction rules, applied in order:
  1. first ```sql fenced block
  2. else first generic ``` fenced block
  3. else text from the first SELECT / WITH keyword to the end
  4. strip trailing semicolons and whitespace
  5. if >1 statement, take the first and flag it

Decided in advance (spec §8.3): extraction failure scores 0 and is NOT retried;
we log extraction_success=false and report the rate per variant.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SQL_FENCE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ANY_FENCE = re.compile(r"```\s*(.*?)```", re.DOTALL)
_SELECT_START = re.compile(r"\b(SELECT|WITH)\b", re.IGNORECASE)
_CONFIDENCE = re.compile(r"CONFIDENCE\s*[:=]\s*([01](?:\.\d+)?|\.\d+)", re.IGNORECASE)


@dataclass
class Extraction:
    sql: str | None
    extraction_success: bool
    confidence: float | None
    multi_statement: bool


def _first_statement(sql: str) -> tuple[str, bool]:
    """Return the first statement and whether more than one was present."""
    # split on ; that terminate statements (naive; SQL literals with ; are rare here)
    parts = [p for p in (s.strip() for s in sql.split(";")) if p]
    if not parts:
        return sql.strip(), False
    return parts[0], len(parts) > 1


def parse_confidence(raw: str) -> float | None:
    m = _CONFIDENCE.search(raw or "")
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return val if 0.0 <= val <= 1.0 else None


def extract(raw: str) -> Extraction:
    confidence = parse_confidence(raw)
    candidate: str | None = None

    m = _SQL_FENCE.search(raw or "")
    if m:
        candidate = m.group(1)
    else:
        m = _ANY_FENCE.search(raw or "")
        if m:
            candidate = m.group(1)
        else:
            m = _SELECT_START.search(raw or "")
            if m:
                candidate = raw[m.start():]

    if candidate is None:
        return Extraction(None, False, confidence, False)

    stmt, multi = _first_statement(candidate)
    stmt = stmt.strip().rstrip(";").strip()
    if not stmt or not _SELECT_START.search(stmt):
        return Extraction(None, False, confidence, multi)
    return Extraction(stmt, True, confidence, multi)
