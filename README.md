# Yardstick

**A pre-registered study of when LLM-generated SQL is safe to trust — and what actually
improves it.**

150 natural-language questions × 3 complexity tiers × 2 prompt strategies × 2 model sizes.
Every generated query executed against a real database and compared to a human-written
gold answer. Statistics chosen in advance and committed to Git before the full run.

> **Status:** results below are final except where marked
> **[provisional]** — one variant (V4) is 90/150 complete because of a free-tier daily
> token cap. This affects only the exploratory interaction test; the pre-registered
> primary result and all three research questions are fully answered.

---

## The question

Teams are increasingly letting LLMs write SQL against production warehouses. The usual
process is: validate on a benchmark, pick the prompt that wins, deploy it everywhere.

**This study asks whether that is safe, and where it stops being safe.**

- **RQ1** — Does few-shot prompting improve execution accuracy, and does the improvement
  differ across query complexity?
- **RQ2** — Can question difficulty be predicted from cheap, LLM-free features and used to
  route to the appropriate model?
- **RQ3** — Does self-reported confidence predict correctness, and does cross-variant
  agreement predict it better?

The framing that matters: **a SQL query that throws a syntax error is a visible failure.
A query that executes cleanly and returns plausible but wrong numbers is an invisible
one.** The second kind flows into dashboards and decisions. This study measures how often
it happens, and finds it gets *worse* as models get better.

---

## Headline findings

**1. The better the model, the higher the share of its errors that are silent.**
Every single error made by the most accurate variant (V3, 89% accurate) executed cleanly
and returned plausible wrong numbers — **100% silent**. The weakest variant at least failed
loudly 11% of the time. Across all variants, **82–96% of errors were silent** depending on
tier. Choosing a model by benchmark score alone selects for *quieter*, not fewer, dangers.

**2. Few-shot prompting produced no statistically significant benefit at any complexity
tier.** Lift was −2 pts (simple), 0 pts (moderate), +8 pts (complex); all p ≈ 1.0 after
Benjamini–Hochberg correction. A 10-question pilot had suggested few-shot nearly doubled
accuracy on complex queries (33% → 67%); at n=50 that collapsed to non-significance.
Pre-registration is the only reason this is reported as a null instead of a discovery.

**3. Model size mattered ~3.5× more than prompt engineering — but only on hard queries.**
Upgrading 8B → 70B gave **+28 pts on complex queries (95% CI [+14, +42], p = 0.0013)**,
versus few-shot's non-significant +8. On moderate queries the model upgrade gave **exactly
zero** (both 82%). Effort spent on prompts was effort spent on the wrong lever.

**4. Self-reported confidence is nearly useless; cross-model agreement works.** All
variants were overconfident — the weakest claimed **99% confidence while being 77% correct**
(ECE 0.219). For predicting correctness, cross-variant result-set agreement scored
**AUC 0.857** versus **0.643** for self-reported confidence. Asking "do two models agree?"
beats asking a model "are you sure?"

**5. Difficulty routing failed to beat random.** My 6-feature difficulty model (AUC 0.665)
was *outperformed by question length alone* (0.724). Routing retained 88.7% of the
expensive model's accuracy at 28% of its cost — but **random routing at the same budget
matched it exactly** (both 78.3% accuracy). Reported as the negative result it is.

---

## Method

### Design

A 2×2 factorial (prompt strategy × model size) run across three complexity tiers.

| Variant | Prompt | Model | Role |
|---|---|---|---|
| V1 | zero-shot | Llama-3.1-8B | baseline, cheapest |
| V2 | few-shot | Llama-3.1-8B | prompt effect |
| V3 | zero-shot | Llama-3.3-70B | model effect |
| V4 | few-shot | Llama-3.3-70B | interaction |

Both models run on Groq's free tier. Cost is computed per call from **published
per-token list prices** (8B: $0.05/$0.08 per Mtok; 70B: $0.59/$0.79), which is what makes
the routing cost analysis meaningful despite $0 actual spend.

### Data

[Spider](https://yale-lily.github.io/spider) (Yale LILY, CC BY-SA 4.0) — the only major
text-to-SQL benchmark that ships **executable SQLite databases**, which execution accuracy
requires.

- **150 questions**, 50 per tier, capped at 3 per database (93 distinct databases).
- **Tiers are externally defined**, not by my judgment: the official Spider
  `eval_hardness()` function classifies each gold query, mapped easy→simple,
  medium→moderate, hard+extra→complex.
- **Ground truth was validated, not assumed.** Every gold query was executed; 7 returning
  zero rows were excluded (they make execution comparison degenerate), and 20 questions
  were hand-read for ambiguity. **Two were excluded for broken gold SQL** — both contained
  a cartesian self-join bug (`ON T2.actid = T2.actid`) and selected the wrong column.
- Fixed seed throughout. Train/test split (90/60) assigned **before** any feature
  engineering, with **whole databases kept on one side** so no schema spans both splits.

### Metric

**Execution accuracy** — binary per question. 1 if the generated query executes without
error *and* its result set matches the gold query's, else 0. No LLM judge; correctness is
objective.

Result-set comparison rules (`set_match`, the primary flag):

| Rule | Decision |
|---|---|
| Row order | **Ignored** (`exact_match` recorded separately for the order-sensitive view) |
| Column order / names | Ignored — values compared as sorted tuples |
| Duplicate rows | **Preserved** — multiset comparison, so `DISTINCT` remains a real difference |
| Floats | Rounded to 4 dp |
| NULL | `NULL == NULL` |
| Empty gold results | Excluded at sampling time |

**Extraction failures score 0 and are not retried** — a model that can't emit parseable SQL
is a real production problem. (In practice: 0 extraction failures across 540 valid cells.)

### Execution safety

Generated SQL is untrusted input. Every query ran against a **read-only copy** of the
database (`file:...?mode=ro`, `chmod 0444`), with a **30-second timeout** and a
**10,000-row cap**. The cap fired usefully: one V1 query added a spurious join and tried to
return >10k rows.

### Statistics

- **McNemar's exact test** for the primary comparison — the correct test for paired binary
  outcomes. (A paired t-test on binary data is the classic error here and was avoided.)
- **Bootstrap 95% CIs**, 10,000 resamples, resampling *questions* to preserve pairing.
- **Benjamini–Hochberg FDR** across the three pre-registered primary comparisons.
- Exploratory analyses (model effect, interaction, routing, calibration, taxonomy) are
  reported **uncorrected and labeled exploratory**, per the pre-registration.

### Pre-registration and scorer validation

- **[`PREREGISTRATION.md`](PREREGISTRATION.md)** was committed to Git *before* the full run.
  The commit timestamp is the proof. It fixes the hypothesis, metric, test, correction, and
  the replicate decision, and records the pilot evidence behind them.
- **Power:** the pilot gave a minimum detectable effect at n=50 of roughly **+14 to +27
  percentage points** depending on baseline. The study is powered for *large* effects only —
  stated up front, not discovered afterward.
- **Replicates:** at temperature 0, `set_match` was identical across 3 replicates in all 40
  pilot cells, so the full run uses 1 replicate. (Raw SQL text varied in 3/40 cells on the
  70B model without changing any verdict.)
- **Our scorer was cross-validated against the official Spider evaluation script**:
  **18/19 agreement (95%)** on cases both could score. The single disagreement is a
  documented *spurious match* (two structurally different queries both returning `12`) —
  the known limitation of single-instance execution accuracy, not a bug. The official
  parser could not score 11 of 30 predictions at all; ours executed every one. See
  [`docs/scorer_crosscheck.md`](docs/scorer_crosscheck.md).

---

## Results

### Accuracy and silent-failure rate

Accuracy (`set_match`) with silent-failure rate in parentheses:

| Tier | V1 (8B zero) | V2 (8B few) | V3 (70B zero) | V4 (70B few) |
|---|---|---|---|---|
| Simple | 0.88 (0.12) | 0.86 (0.14) | **0.96 (0.04)** | 0.92 (0.05) *[provisional, n=37]* |
| Moderate | 0.82 (0.18) | 0.82 (0.16) | 0.82 (0.18) | *[insufficient data, n=3]* |
| Complex | 0.60 (0.32) | 0.68 (0.22) | **0.88 (0.12)** | 0.84 (0.16) |

### RQ1 — Does few-shot lift depend on query complexity?

**No. There is no significant lift to depend on anything.**

| Tier | V1 | V2 | Lift | 95% CI | Discordant (V1-only / V2-only) | McNemar p | BH-adj p |
|---|---|---|---|---|---|---|---|
| Simple | 0.880 | 0.860 | −2.0 pts | [−6.0, 0.0] | 1 / 0 | 1.000 | 1.000 |
| Moderate | 0.820 | 0.820 | +0.0 pts | [−12.0, +12.0] | 4 / 4 | 1.000 | 1.000 |
| Complex | 0.600 | 0.680 | +8.0 pts | [−6.0, +22.0] | 5 / 9 | 0.424 | 1.000 |

**H1 is not supported.** The direction is positive on complex and the CI reaches +22, so a
real moderate-sized effect there cannot be ruled out — "not significant" is not "proven
zero," and at n=50 this study can only detect large effects.

### Exploratory: the model effect (uncorrected)

| Tier | Comparison | Lift | 95% CI | McNemar p |
|---|---|---|---|---|
| Simple | V3 vs V1 (zero-shot) | +8 pts | [+2, +16] | 0.125 |
| Moderate | V3 vs V1 | +0 pts | [−10, +10] | 1.000 |
| **Complex** | **V3 vs V1** | **+28 pts** | **[+14, +42]** | **0.0013** |
| Complex | V4 vs V2 (few-shot) | +16 pts | [+4, +30] | 0.039 |
| Complex | V4 vs V3 (prompt, on 70B) | −4 pts | [−12, +4] | 0.625 |

The model effect is large and significant on complex queries under *both* prompt
strategies. Adding examples to the strong model did nothing. The interaction contrast
(does few-shot help the strong model more?) was −12 pts, CI [−28, +4] — not significant,
directionally suggesting few-shot helps the *weak* model more. *[provisional]*

On simple queries the bootstrap CI excludes zero while McNemar does not (p = 0.125);
McNemar is conservative with few discordant pairs, and the pre-specified test governs — so
simple is reported as **suggestive, not significant**.

### RQ2 — Can difficulty be predicted and routed on?

Target: "hard" = the cheap model got it wrong (base rate 0.23). Features are computed
**only from the question text and schema DDL** — never from the gold SQL, which does not
exist at inference time. That constraint is enforced by code comment and code review.

**Predicting difficulty (AUC on the 60-question held-out test set):**

| Predictor | AUC |
|---|---|
| **Question length only** (1 feature) | **0.724** |
| Difficulty model (6 features) | 0.665 |
| Schema size only | 0.507 |
| Random | ~0.32 |

**The simplest possible baseline beat the real model.** Adding features hurt.
Generalization was weak: leave-one-tier-out fell to chance on complex (0.525), while
leave-one-**database**-out (93 folds, unseen schemas) held at 0.670. The predictor
recovered Spider's human difficulty labels at 51.7% vs 33% chance — modest, and it
systematically mistook complex for moderate.

**Routing simulation** (test split, n=60; escalation budget k=18 matched to the oracle):

| Policy | Accuracy | Cost | % of expensive acc | % of expensive cost |
|---|---|---|---|---|
| always_cheap | 0.700 | $0.0018 | 79.2% | 8.7% |
| always_expensive | 0.883 | $0.0205 | 100% | 100% |
| random | 0.783 | $0.0073 | 88.7% | 35.5% |
| length_only | 0.750 | $0.0085 | 84.9% | 41.2% |
| **difficulty_routed** | **0.783** | **$0.0058** | **88.7%** | **28.0%** |
| **oracle** | **0.900** | $0.0076 | 101.9% | 36.8% |

Difficulty routing retained 88.7% of the expensive model's accuracy at 28% of its cost —
**but random routing matched it on accuracy.** The predictor bought no accuracy over a coin
flip. A 51-point threshold sweep is in
[`results/routing_threshold_sweep.csv`](results/routing_threshold_sweep.csv).

**Two findings worth more than the routing number itself:**

- **The oracle (0.900) beat always-expensive (0.883)** while costing 63% less. Sometimes
  the cheap model is right where the strong one is wrong, so *perfect* routing would be
  both cheaper and more accurate. Real headroom exists; my predictor just couldn't reach it.
- **Cost and difficulty are decoupled.** Question length predicts difficulty (r = 0.55) but
  not cost. Schema size predicts **cost** (r = 0.95) and difficulty *not at all* (AUC
  0.507). The thing that makes a query expensive is not the thing that makes it hard —
  which is precisely why naive cost-based routing misfires.

### RQ3 — Is confidence calibrated, and does agreement predict error better?

**Calibration** (confidence requested on every generation, 0.0–1.0):

| Variant | Mean stated confidence | Actual accuracy | ECE | Verdict |
|---|---|---|---|---|
| V1 | 0.986 | 0.767 | 0.219 | severely overconfident |
| V2 | 0.939 | 0.787 | 0.152 | overconfident |
| V3 | 0.984 | 0.887 | 0.097 | overconfident |
| V4 | 0.923 | 0.856 | 0.067 | overconfident *[provisional]* |

Every variant is overconfident, and the weakest is the worst: **it claims 99% confidence
while being wrong 23% of the time.** Reliability-curve data:
[`results/calibration.csv`](results/calibration.csv).

**Signal comparison** — AUC for predicting `set_match` (0.5 = useless):

| Signal | AUC | Needs gold answer? |
|---|---|---|
| **Cross-variant result-set agreement** | **0.857** | No |
| AST (structural) agreement | 0.698 | No |
| Self-reported confidence | 0.643 | No |

**Cross-variant agreement decisively beats self-reported confidence** — and it is available
in production, since noticing that two models disagree requires no ground truth.

**The practical policy this yields:**

| Flag rule | Outputs flagged | Errors caught | False alarms |
|---|---|---|---|
| **Result-set disagreement** | **28%** | **82%** | **16%** |
| AST disagreement | 74% | 100% | 68% |

Review the 28% of queries where two cheap models disagree and you catch 82% of all errors.
AST-based flagging is too noisy to be useful.

### Silent failures: where models fail invisibly

**Share of each variant's errors that were silent** (executed cleanly, wrong result):

| Variant | Accuracy | Errors | Silent share | Mean confidence *when wrong* |
|---|---|---|---|---|
| V1 (8B zero) | 0.767 | 35 | 89% | 0.963 |
| V2 (8B few) | 0.787 | 32 | 81% | 0.927 |
| V4 (70B few) | 0.856 | 13 | 77% | 0.873 *[provisional]* |
| **V3 (70B zero)** | **0.887** | **17** | **100%** | **0.953** |

The most accurate variant made the fewest errors — and **every one of them was silent.** It
also stated 95% confidence on the answers it got wrong. By tier, **82% (complex), 96%
(moderate), and 94% (simple)** of all errors were silent.

**Error taxonomy** (single bucket per failure, via `sqlglot` AST comparison):

| Variant | wrong_join | wrong_filter | wrong_projection | wrong_aggregation | schema_error |
|---|---|---|---|---|---|
| V1 | 16 | 8 | 5 | 2 | 4 |
| V2 | 17 | 5 | 1 | 3 | 6 |
| V3 | 6 | 7 | 2 | 2 | 0 |
| V4 | 3 | 5 | 1 | 1 | 1 |

**Wrong joins dominate the cheap model's failures** (16–17 cases) and are what the model
upgrade fixes best (down to 6). Zero timeouts and zero extraction failures throughout.
Note that `wrong_join`, `wrong_filter`, `wrong_projection`, and `wrong_aggregation` are
*all* silent failure modes — the query runs fine and returns wrong numbers.

---

## Deployment recommendation

1. **Spend on the model, not the prompt — and only where it pays.** The 8B→70B upgrade
   bought +28 pts on complex queries and **nothing** on moderate ones. Few-shot bought
   nothing anywhere. If your workload is mostly simple/moderate lookups, the cheap model is
   already at parity; if it includes multi-join analytical queries, upgrade the model.
2. **Never gate on self-reported confidence.** A model claiming 99% certainty was wrong 23%
   of the time, and stayed ~95% confident on its own errors.
3. **Do gate on cross-model disagreement.** Run two cheap models, compare executed result
   sets, and route disagreements to human review: **28% reviewed, 82% of errors caught.**
   This is the single most actionable result in the study, and it costs one extra cheap call.
4. **Assume wrong answers will look right.** 82–96% of errors executed cleanly. Any
   pipeline that treats "the query ran" as "the query is correct" is unprotected against the
   dominant failure mode. Guardrails belong on *results* (row-count sanity, join-fanout
   checks, reconciliation against known aggregates), not on error handling.
5. **Don't build a difficulty router on surface features without checking a length-only
   baseline first.** Mine lost to it, and both lost to random on accuracy.

---

## Limitations

Stated plainly, because they bound every claim above.

1. **Benchmark contamination.** Spider is public and predates these models' training
   cutoffs; both models may have seen it. Absolute accuracies are therefore likely
   optimistic. This affects all four variants equally, so the *comparative* conclusions —
   which is what the study is about — are more robust than the absolute numbers. Mitigating
   this properly would require a held-out check on BIRD or hand-written questions
   (not done).
2. **Underpowered for small effects.** MDE at n=50 is roughly +14 to +27 pts. The complex
   few-shot lift (+8 pts, CI to +22) could be real and undetected. A null here means "not
   detected at this sample size," not "absent."
3. **Complexity is confounded with question length and schema size.** Harder tiers came
   from bigger databases with longer questions (complex: ~14 tokens / 6 tables; simple: ~9
   tokens / 4 tables), so "complexity effect" cannot be fully separated from "context-length
   effect."
4. **Single-instance execution accuracy admits spurious matches.** The scorer cross-check
   found a case where two semantically different queries returned identical values by
   coincidence and were scored correct. Test-suite evaluation over many fuzzed database
   instances would fix this; it was out of scope.
5. **Uneven database representation.** 150 questions across 93 databases, capped at 3 each,
   so schemas contribute unequally.
6. **SQLite on small benchmark databases is a weak warehouse-performance proxy.** All
   variants' correct queries ran in ~1.1–1.5 ms median, so the query-efficiency dimension is
   effectively uninformative here and no efficiency claim is made.
7. **Cost is list-price, not billed.** Actual spend was $0 on a free tier; the routing
   economics assume published per-token rates hold at scale.
8. **Model-size and provider are not separable.** Both models are Llama variants on one
   provider, so "model effect" means *size/capability within one family*, not a
   cross-vendor comparison.
9. **The moderate tier's train/test split is 33/17, not 30/20**, a side effect of keeping
   whole databases on one side of the split. No-leakage was prioritized over an exact ratio.
10. **V4 is incomplete (90/150).** A free-tier daily token cap blocked ~60 cells. Only the
    exploratory interaction test and V4's simple/moderate numbers are affected; every
    pre-registered result and all three RQ answers use complete data.

---

## Reproducing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

cp .env.example .env          # add GROQ_API_KEY and a Supabase DATABASE_URL
psql "$DATABASE_URL" -f sql/schema.sql
python scripts/verify_setup.py
```

Then, in order:

```bash
python scripts/download_data.py        # Spider bundle (~206 MB, not committed)
python scripts/make_db_copies.py       # read-only working copies
python scripts/sample_and_validate.py  # sample 150 + validate every gold query
python scripts/load_questions.py       # -> Supabase
python scripts/select_fewshot.py       # held-out few-shot examples

python scripts/run_experiment.py --variant all   # resumable; safe to re-run
python scripts/execute_and_score.py              # separate from generation, zero API cost

python scripts/analyze_primary.py      # RQ1: McNemar + bootstrap + BH
python scripts/analyze_exploratory.py  # model effect, interaction, efficiency
python scripts/report_scoring.py       # silent-failure rate + error taxonomy
python scripts/compute_features.py && python scripts/train_router.py
python scripts/simulate_routing.py     # RQ2
python scripts/analyze_calibration.py  # RQ3
python scripts/export_results.py       # -> results/*.csv
```

**Runtime and cost:** 620 successful generation calls so far (540 matrix cells + 80 pilot
replicates). **$0 actual** (Groq free tier); list-price equivalent **$0.151** total, of
which the 540-cell matrix is $0.126.

**Input tokens dominate: 494k input vs 27k output — a 95/5 split**, because the schema DDL
is included in every prompt. This is why schema size drives cost (r = 0.95) far more than
question complexity does, and it is the mechanism behind the cost/difficulty decoupling in
RQ2.

Wall-clock is dominated by rate limits, not compute — the 70B model's 100k-tokens/day free
cap means the full matrix spans **2–3 days**. Generation is cached and resumable, so
interruption costs nothing; re-scoring is free at any time because executions are stored
separately from generations.

---

## Repository

```
PREREGISTRATION.md          committed before the full run — the timestamp is the point
yardstick/                  sandbox, comparison, taxonomy, stats, features, routing, calibration
scripts/                    one script per pipeline stage, all resumable/idempotent
results/*.csv               every table behind the numbers above
docs/scorer_crosscheck.md   validation against the official Spider evaluator
docs/free_tier_verification.md
third_party/spider_eval/    vendored official Spider scorer (for cross-validation)
yardstick_project_spec.md   the full build specification
```

## Data & attribution

- **Spider** — Yale LILY lab, **CC BY-SA 4.0**, https://yale-lily.github.io/spider.
  Downloaded by `scripts/download_data.py`; no dataset files are committed.
- **Official Spider evaluation scripts** — vendored under `third_party/spider_eval/` from
  https://github.com/taoyds/spider, used for tier labeling and scorer cross-validation.

No LangChain, Ragas, DeepEval, or prebuilt eval framework. The statistical layer is
hand-built on SciPy/statsmodels — that was the point.
