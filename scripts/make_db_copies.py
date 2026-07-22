"""Phase 1 — make read-only working copies of the sampled databases (spec §8.2).

Generated SQL is untrusted; we always open databases read-only, but the spec also
requires working on COPIES so the pristine download can never be mutated. This copies
each sampled question's database into databases/<db_id>/<db_id>.sqlite and marks the
file read-only (chmod 0444). databases/ is gitignored.

Run:  python scripts/make_db_copies.py
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from yardstick import spider_data as sd

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "data" / "questions.json"


def main() -> int:
    db_ids = sorted({q["db_id"] for q in json.loads(QUESTIONS.read_text())})
    print(f"{len(db_ids)} distinct databases to copy.\n")

    copied, total_bytes = 0, 0
    for db_id in db_ids:
        src = sd.db_sqlite_path(db_id)
        dst = sd.DBS / db_id / f"{db_id}.sqlite"
        if not src.exists():
            print(f"  ⚠ missing original: {db_id}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.chmod(0o644)   # allow overwrite on re-run
            dst.unlink()
        shutil.copy2(src, dst)
        dst.chmod(0o444)       # read-only at the filesystem level
        copied += 1
        total_bytes += dst.stat().st_size

    print(f"Copied {copied} databases ({total_bytes/1e6:.1f} MB) into {sd.DBS}")
    print("All copies are chmod 0444 (read-only). Execution uses spider_data.working_db_path().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
