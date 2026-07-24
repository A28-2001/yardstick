"""Calibration and cross-variant agreement (spec §12).

Three candidate signals for "is this generated query actually correct?", all available
at inference time (no gold answer needed):

  1. self_confidence      — what the model says about itself (§12.2)
  2. result-set agreement — do the variants' EXECUTED results match each other? (§12.3)
  3. AST agreement        — do their query structures match? (§12.3)

We test whether each predicts correctness, rather than assuming confidence works.
A poorly calibrated model is itself the finding.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import sqlglot


def ece(confidences, correct, n_bins: int = 10):
    """Expected Calibration Error + the reliability-curve bins.

    ECE = sum_b (n_b/N) * |accuracy_b - mean_confidence_b|.  0 = perfectly calibrated.
    Returns (ece, bins) where each bin is (lo, hi, n, mean_conf, accuracy).
    """
    conf = np.asarray(confidences, dtype=float)
    acc = np.asarray(correct, dtype=float)
    keep = ~np.isnan(conf)
    conf, acc = conf[keep], acc[keep]
    if len(conf) == 0:
        return float("nan"), []

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total, bins = len(conf), []
    err = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        # last bin is inclusive of 1.0
        m = (conf >= lo) & (conf < hi) if hi < 1.0 else (conf >= lo) & (conf <= hi)
        n = int(m.sum())
        if n == 0:
            bins.append((lo, hi, 0, float("nan"), float("nan")))
            continue
        c, a = float(conf[m].mean()), float(acc[m].mean())
        err += (n / total) * abs(a - c)
        bins.append((lo, hi, n, c, a))
    return float(err), bins


def pairwise_agreement(values: list) -> float:
    """Fraction of variant PAIRS that agree. None values are ignored.
    Returns NaN if fewer than two comparable values."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return float("nan")
    pairs = list(combinations(vals, 2))
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def canonical_sql(sql: str | None) -> str | None:
    """Normalised SQL for structural comparison; None if unparseable/empty."""
    if not sql:
        return None
    try:
        return sqlglot.parse_one(sql, read="sqlite").sql(dialect="sqlite", normalize=True)
    except Exception:  # noqa: BLE001
        return " ".join(sql.lower().split())


def flag_stats(flagged: np.ndarray, correct: np.ndarray) -> dict:
    """If we escalate every FLAGGED item to human review, how well does it work?

    recall      — fraction of actual errors that get caught
    false_alarm — fraction of correct answers needlessly flagged
    """
    flagged = np.asarray(flagged, bool)
    errors = ~np.asarray(correct, bool)
    n_err, n_ok = int(errors.sum()), int((~errors).sum())
    return {
        "flag_rate": float(flagged.mean()),
        "errors_caught": int((flagged & errors).sum()),
        "recall": float((flagged & errors).sum() / n_err) if n_err else float("nan"),
        "false_alarm_rate": float((flagged & ~errors).sum() / n_ok) if n_ok else float("nan"),
    }
