"""Loaders for the extracted Spider bundle.

Reads the bundle root recorded by scripts/download_data.py and exposes:
  - examples: merged train + dev question/SQL/parsed-sql records
  - db sqlite path lookup
  - schema DDL extraction straight from each SQLite file (spec §13.2:
    CREATE TABLE statements with types + FKs, indexes stripped, held constant)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
DBS = REPO / "databases"  # read-only working copies of the sampled databases


def bundle_root() -> Path:
    marker = DATA / "BUNDLE_ROOT"
    if not marker.exists():
        raise RuntimeError("Bundle not downloaded yet. Run: python scripts/download_data.py")
    return Path(marker.read_text().strip())


def load_examples() -> list[dict]:
    """All train_spider + dev examples, each tagged with its source split.

    Each record has: db_id, query (gold SQL), question, sql (parsed dict), split.
    'split' here is the Spider origin (train/dev); our experiment train/test
    assignment is a separate column decided later in Phase 1.
    """
    root = bundle_root()
    out: list[dict] = []
    for fname, origin in [("train_spider.json", "train"), ("dev.json", "dev")]:
        path = root / fname
        if not path.exists():
            continue
        for rec in json.loads(path.read_text()):
            rec["spider_origin"] = origin
            out.append(rec)
    return out


def db_sqlite_path(db_id: str) -> Path:
    """The pristine ORIGINAL from the downloaded bundle (source of truth)."""
    return bundle_root() / "database" / db_id / f"{db_id}.sqlite"


def working_db_path(db_id: str) -> Path:
    """The read-only working COPY under databases/ (spec §8.2 — never touch originals).

    Falls back to the bundle original if the copy hasn't been made yet, so callers
    keep working before scripts/make_db_copies.py has run.
    """
    copy = DBS / db_id / f"{db_id}.sqlite"
    return copy if copy.exists() else db_sqlite_path(db_id)


def readonly_uri(path: Path) -> str:
    """SQLite read-only URI (spec §8.2). Never opens a DB writable."""
    return f"file:{path}?mode=ro"


def extract_schema_ddl(db_id: str) -> str:
    """Concatenated CREATE TABLE statements from the DB (tables only, no indexes).

    Pulled from sqlite_master so it reflects the real schema, including column
    types, primary keys, and foreign keys. Held constant across all variants.
    """
    path = db_sqlite_path(db_id)
    con = sqlite3.connect(readonly_uri(path), uri=True)
    try:
        rows = con.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    stmts = [r[0].strip().rstrip(";") + ";" for r in rows]
    return "\n\n".join(stmts)
