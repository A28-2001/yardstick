"""Safe SQLite execution sandbox (spec §8.2).

Every query, gold or model-generated, runs through here:
  - database opened READ-ONLY (file:...?mode=ro), so nothing can mutate it
  - hard timeout via a watchdog thread that calls Connection.interrupt()
  - returned rows capped
  - every exception caught and reported, never crashes the caller

Detailed error-type taxonomy (syntax/schema/etc., spec §9.5) is layered on in
Phase 3; this module reports the raw error + whether it timed out.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_S = 30.0
ROW_CAP = 10_000


@dataclass
class ExecResult:
    executed: bool                 # did the query run to completion and return rows
    rows: list[tuple] | None
    row_count: int | None
    col_count: int | None
    error: str | None
    timed_out: bool
    truncated: bool                # hit ROW_CAP
    execution_time_ms: float


def execute(db_path: str | Path, sql: str,
            timeout_s: float = TIMEOUT_S, row_cap: int = ROW_CAP) -> ExecResult:
    uri = f"file:{db_path}?mode=ro"
    start = time.perf_counter()
    timed_out = threading.Event()

    try:
        con = sqlite3.connect(uri, uri=True, timeout=timeout_s)
    except sqlite3.Error as e:
        return ExecResult(False, None, None, None, f"connect failed: {e}", False, False,
                          (time.perf_counter() - start) * 1000)

    def _watchdog():
        timed_out.set()
        con.interrupt()  # documented safe to call from another thread

    timer = threading.Timer(timeout_s, _watchdog)
    timer.start()
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(row_cap)
        truncated = cur.fetchone() is not None
        col_count = len(cur.description) if cur.description else 0
        elapsed = (time.perf_counter() - start) * 1000
        return ExecResult(True, [tuple(r) for r in rows], len(rows), col_count,
                          None, False, truncated, elapsed)
    except sqlite3.Error as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ExecResult(False, None, None, None, str(e), timed_out.is_set(), False, elapsed)
    finally:
        timer.cancel()
        con.close()
