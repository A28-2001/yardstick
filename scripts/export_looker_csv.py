"""Flatten the run matrix into one CSV shaped for Looker Studio.

Deliberately different from export_web_data.py. That one optimises for wire size
because the browser downloads it on every page load. This one optimises for what
Looker's chart builder can consume without the reader writing calculated fields.

Three shaping decisions worth stating, because none of them are obvious and all
three cost an afternoon to rediscover:

1. Booleans ship as 1/0 integers. Looker aggregates numbers happily and booleans
   awkwardly, so AVG(correct) is an accuracy rate straight out of the box.

2. Tier ships alongside tier_order. Looker sorts a text dimension alphabetically,
   which turns simple/moderate/complex into complex/moderate/simple on every axis.
   Sorting a chart by tier_order fixes it once per chart.

3. Variant names are spelled out. Dimension values appear raw in legends, and
   "V3" tells a reader nothing.

Run:  python scripts/export_looker_csv.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "docs" / "data" / "runs.json"
OUT = REPO / "docs" / "data" / "yardstick_runs.csv"

TIER_ORDER = {"simple": 1, "moderate": 2, "complex": 3}

COLUMNS = [
    "run_id", "variant", "model", "prompt_strategy",
    "tier", "tier_order", "database",
    "question", "gold_sql", "generated_sql",
    "outcome", "correct", "executed", "silent_failure", "error_type",
    "confidence", "confidence_bucket",
    "gold_rows", "returned_rows",
    "tokens", "cost_usd", "latency_ms",
]


def outcome_of(run: dict) -> str:
    """The single most useful dimension on the whole sheet.

    Splits wrong answers by whether anything visibly went wrong, which is the
    distinction the entire study is about. A bar chart of this column is the
    dashboard's headline in one control.
    """
    if run["ok"]:
        return "Correct"
    if run["ran"]:
        return "Silent failure"
    return "Loud error"


def confidence_bucket(conf: float | None) -> str:
    if conf is None:
        return "unreported"
    if conf >= 0.9:
        return "0.9 to 1.0"
    if conf >= 0.7:
        return "0.7 to 0.9"
    if conf >= 0.5:
        return "0.5 to 0.7"
    return "below 0.5"


def main() -> int:
    runs = json.loads(SRC.read_text())["runs"]

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for i, r in enumerate(runs, start=1):
            w.writerow({
                "run_id": i,
                "variant": r["v"],
                "model": f"Llama 3.1 {r['m']}",
                "prompt_strategy": r["p"],
                "tier": r["t"],
                "tier_order": TIER_ORDER[r["t"]],
                "database": r["db"],
                "question": r["q"],
                "gold_sql": r["gold"],
                "generated_sql": r["sql"],
                "outcome": outcome_of(r),
                "correct": int(r["ok"]),
                "executed": int(r["ran"]),
                "silent_failure": int(r["silent"]),
                "error_type": r["err"] or "none",
                "confidence": r["conf"],
                "confidence_bucket": confidence_bucket(r["conf"]),
                "gold_rows": r["grows"],
                "returned_rows": r["prows"],
                "tokens": r["tok"],
                # plain decimal, not 3e-05: Sheets parses the exponent fine but
                # shows it verbatim in the cell, which reads like a defect
                "cost_usd": f"{r['cost']:.6f}",
                "latency_ms": r["ms"],
            })

    kb = OUT.stat().st_size / 1024
    n_correct = sum(r["ok"] for r in runs)
    n_silent = sum(r["silent"] for r in runs)
    n_loud = sum(1 for r in runs if not r["ok"] and not r["ran"])

    print(f"wrote {OUT.relative_to(REPO)}  {len(runs)} rows  {kb:.0f} KB")
    print(f"  Correct {n_correct}   Silent failure {n_silent}   Loud error {n_loud}")
    print(f"  sanity: {n_correct + n_silent + n_loud} == {len(runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
