"""Phase 1, Step 1 — acquire the Spider bundle (with executable SQLite DBs).

Downloads the official Spider dataset zip from Google Drive (CC BY-SA 4.0),
extracts it, inventories the contents, and records where the bundle lives.
Nothing here is committed — data/ is gitignored (spec §6.2).

Idempotent: skips the download/extract if the bundle is already present.

Run:  python scripts/download_data.py
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import gdown

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
ZIP_PATH = DATA / "spider_data.zip"

# Official Spider bundle (includes database/, tables.json, train_spider.json, dev.json).
# Source: https://yale-lily.github.io/spider  (CC BY-SA 4.0, Yale LILY lab)
SPIDER_GDRIVE_ID = "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"


def find_bundle_root(base: Path) -> Path | None:
    """Locate the extracted folder that holds both tables.json and database/."""
    if (base / "tables.json").exists() and (base / "database").is_dir():
        return base
    for p in base.rglob("tables.json"):
        if (p.parent / "database").is_dir():
            return p.parent
    return None


def main() -> int:
    DATA.mkdir(exist_ok=True)

    root = find_bundle_root(DATA)
    if root is None:
        if not ZIP_PATH.exists():
            print(f"Downloading Spider bundle (~1 GB) from Google Drive id={SPIDER_GDRIVE_ID}")
            print("This is the slow step; it only happens once.\n")
            gdown.download(id=SPIDER_GDRIVE_ID, output=str(ZIP_PATH), quiet=False)
        else:
            print(f"Zip already present at {ZIP_PATH} ({ZIP_PATH.stat().st_size/1e6:.0f} MB)")
        print("\nExtracting ...")
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(DATA)
        root = find_bundle_root(DATA)

    if root is None:
        print("ERROR: after extraction, could not find tables.json + database/.")
        print(f"Inspect {DATA} manually.")
        return 1

    print(f"\nBundle root: {root}")

    # Inventory — confirm the pieces the rest of Phase 1 needs.
    print("\nContents:")
    for f in ["tables.json", "train_spider.json", "train_others.json", "dev.json",
              "train_gold.sql", "dev_gold.sql"]:
        print(f"  {'✓' if (root / f).exists() else '—'} {f}")

    db_root = root / "database"
    db_dirs = sorted(d for d in db_root.iterdir() if d.is_dir())
    sqlite_files = list(db_root.rglob("*.sqlite"))
    print(f"\n  databases: {len(db_dirs)} db folders, {len(sqlite_files)} .sqlite files")
    missing_sqlite = [d.name for d in db_dirs if not (d / f"{d.name}.sqlite").exists()]
    if missing_sqlite:
        print(f"  ⚠ {len(missing_sqlite)} db folders have no <db>.sqlite (e.g. {missing_sqlite[:5]})")

    (DATA / "BUNDLE_ROOT").write_text(str(root))
    print(f"\nRecorded bundle root at {DATA/'BUNDLE_ROOT'}")
    print("Done — Step 1 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
