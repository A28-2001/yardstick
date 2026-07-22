# Pre-registration — Yardstick

**Committed before the full experiment was run.** The Git commit timestamp of this
file is the pre-registration timestamp. Pilot evidence (10 questions × 4 variants ×
3 replicates) informed the sample-size and replicate decisions below; the full 150-
question experiment had NOT been run when this was committed.

*Finalized 2026-07-22 with the pilot numbers below, and committed before the full run.*

## Design

2×2 factorial across three complexity tiers (tiers = official Spider hardness:
easy→simple, medium→moderate, hard+extra→complex).

| Variant | Prompt | Model |
|---|---|---|
| V1 | zero-shot | Llama-3.1-8B (cheap) |
| V2 | few-shot | Llama-3.1-8B (cheap) |
| V3 | zero-shot | Llama-3.3-70B (strong) |
| V4 | few-shot | Llama-3.3-70B (strong) |

150 questions, 50 per tier, capped at 3 per database, fixed seed. Everything runs on
Groq's free tier; the "model" factor is model **size** (cheap 8B vs strong 70B), and
cost is computed from published list prices as the routing cost proxy (§13.3).

## Primary hypothesis

**H1:** The execution-accuracy lift of few-shot prompting over zero-shot (V2 − V1)
differs significantly across query complexity tiers.

## Primary metric

Execution accuracy: binary per question. 1 if the generated query executes without
error AND its result set matches the gold query's result set under the §9.2 comparison
rules (`set_match`: order-insensitive unless the gold query has ORDER BY; column order
and names ignored; duplicates preserved; floats rounded to 4 dp). Otherwise 0.

## Primary comparison

V2 vs V1, within each complexity tier, using **McNemar's exact test** on paired binary
outcomes (not a t-test). Three comparisons (simple, moderate, complex).

**All three tiers are retained** in the primary analysis. H1 predicts the lift *differs*
across tiers, so a tier where few-shot shows little or no lift (e.g. because accuracy is
near-saturated) is an informative contrast, not a reason for exclusion. The pilot hints
that lift concentrates on the complex tier (below); confirming that pattern in the full
run is exactly what H1 is about.

## Correction

Benjamini–Hochberg FDR across the primary comparisons only.

## Significance threshold

alpha = 0.05.

## Replicate decision

Pilot: 10 questions × 4 variants × **3 replicates** at temperature 0. `set_match` was
**identical across all 3 replicates in all 40 cells (zero variance)**. **DECISION: the
full run uses 1 replicate per cell.** At temperature 0 the output is deterministic, so
this is a token saving (~⅔) with no measurable loss of information.

## Sample-size justification / power

From the pilot proportions (conservative *unpaired* normal approximation, α=0.05,
power=0.80, two-sided; the paired McNemar test used for the primary analysis needs fewer):

- **complex:** pilot V1=0.33 → V2=0.67 (Cohen's h ≈ 0.68) requires ≈ **34 per group** →
  **n=50 is adequately powered** to detect a lift of this magnitude on the complex tier.
- **simple / moderate:** pilot lift ≈ 0 (few-shot ≈ zero-shot), so there is no effect to
  size; if the full run confirms near-saturation, the correct outcome is a non-significant
  McNemar result there.
- **Minimum detectable effect at n=50** (unpaired): Cohen's h ≈ 0.56, i.e. roughly a
  **+14 to +27 percentage-point** lift depending on baseline (≈+14pts at an 85% baseline,
  ≈+21pts at 70%, ≈+27pts at 50%).

**Stated limitation:** at n=50 per tier the study is powered to detect **large** effects.
Subtle differences (< ~15pts), and any difference on a near-ceiling tier, may not reach
significance. This is accepted rather than inflating n.

## Pilot findings that shaped this pre-registration

- **Extraction failures 0/120, timeouts 0/120** — the pipeline is sound; the full run is safe.
- **Ceiling/floor (pilot n per tier is small — 4/3/3 — so indicative only):** no floor on
  complex (V1=0.33, above the 15% floor; V3=1.00). Moderate sat at 1.00 for every variant
  and simple at 0.75; combined with the 30-question V1 check (simple 0.90, moderate 1.00,
  complex 0.70) this suggests lift will concentrate on **complex**, with simple/moderate
  near saturation. **No tier is dropped** (see Primary comparison) — a saturated tier
  showing no lift is a valid part of the H1 pattern.
- **Replicate variance zero** (see above) → 1 replicate.

## Pre-specified secondary metric

**Silent-failure rate**: proportion of generated queries that execute successfully but
return a non-matching result set. Reported per variant per tier, uncorrected, labeled
exploratory.

## Everything else is exploratory

Model effect (V3 vs V1), the interaction (V4), query efficiency, routing performance,
the difficulty predictor, calibration (self-confidence + cross-variant agreement), and
the error taxonomy are all labeled exploratory and reported without correction, with
that status stated explicitly.
