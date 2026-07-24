"""Statistical methods (spec §10). Built by hand on scipy/statsmodels primitives.

For the primary comparison (V2 vs V1, paired binary set_match within a tier):
  - McNemar's EXACT test (not a t-test — the classic error on paired binary data, §10.1)
  - bootstrap 95% CI on the accuracy difference, resampling QUESTIONS to preserve pairing (§10.2)
  - Benjamini-Hochberg FDR across the primary comparisons (§10.4)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


@dataclass
class PairedResult:
    n: int
    acc_a: float          # control (e.g. V1)
    acc_b: float          # treatment (e.g. V2)
    diff_pts: float       # (acc_b - acc_a) in percentage points
    both_correct: int
    a_only: int           # a correct, b wrong  (discordant)
    b_only: int           # b correct, a wrong  (discordant)
    both_wrong: int
    p_value: float        # McNemar exact
    ci_low_pts: float
    ci_high_pts: float


def paired_counts(a: list[int], b: list[int]) -> tuple[int, int, int, int]:
    """(both_correct, a_only, b_only, both_wrong) for paired 0/1 outcomes."""
    both_correct = sum(1 for x, y in zip(a, b) if x and y)
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if not x and y)
    both_wrong = sum(1 for x, y in zip(a, b) if not x and not y)
    return both_correct, a_only, b_only, both_wrong


def mcnemar_exact(a: list[int], b: list[int]) -> float:
    both_correct, a_only, b_only, both_wrong = paired_counts(a, b)
    table = [[both_correct, a_only], [b_only, both_wrong]]
    return float(mcnemar(table, exact=True).pvalue)


def bootstrap_ci_diff(a: list[int], b: list[int], n_boot: int = 10000,
                      seed: int = 20260721, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI (in pts) on mean(b) - mean(a), resampling paired questions."""
    a_arr, b_arr = np.asarray(a, float), np.asarray(b, float)
    n = len(a_arr)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    diffs = (b_arr[idx].mean(axis=1) - a_arr[idx].mean(axis=1)) * 100
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def compare_paired(a: list[int], b: list[int], seed: int = 20260721) -> PairedResult:
    bc, ao, bo, bw = paired_counts(a, b)
    n = len(a)
    acc_a, acc_b = (sum(a) / n, sum(b) / n) if n else (float("nan"), float("nan"))
    lo, hi = bootstrap_ci_diff(a, b, seed=seed) if n else (float("nan"), float("nan"))
    return PairedResult(
        n=n, acc_a=acc_a, acc_b=acc_b, diff_pts=(acc_b - acc_a) * 100,
        both_correct=bc, a_only=ao, b_only=bo, both_wrong=bw,
        p_value=mcnemar_exact(a, b) if n else float("nan"),
        ci_low_pts=lo, ci_high_pts=hi)


def benjamini_hochberg(pvals: list[float], alpha: float = 0.05):
    """Return (reject_flags, adjusted_pvals) under BH FDR."""
    reject, p_adj, _, _ = multipletests(pvals, alpha=alpha, method="fdr_bh")
    return list(reject), list(p_adj)


def diff_in_diff(v1: list[int], v2: list[int], v3: list[int], v4: list[int],
                 n_boot: int = 10000, seed: int = 20260721, alpha: float = 0.05):
    """2x2 interaction contrast (spec §4.1): does few-shot help the strong model MORE
    than the cheap model?  DiD = (acc_V4 - acc_V3) - (acc_V2 - acc_V1), in pts, with a
    bootstrap CI resampling the shared questions (all four variants paired per question).
    Returns (point_pts, lo_pts, hi_pts).
    """
    a1, a2, a3, a4 = (np.asarray(x, float) for x in (v1, v2, v3, v4))
    n = len(a1)
    point = ((a4.mean() - a3.mean()) - (a2.mean() - a1.mean())) * 100
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot = ((a4[idx].mean(1) - a3[idx].mean(1)) - (a2[idx].mean(1) - a1[idx].mean(1))) * 100
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(point), float(lo), float(hi)
