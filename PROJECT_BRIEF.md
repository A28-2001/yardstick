# Project brief: Yardstick (for resume writing)

Self-contained summary of one project. Everything below is factual and verifiable at the
links. Written to be pasted into a fresh conversation as source material.

---

## Identity

| | |
|---|---|
| **Name** | Yardstick |
| **One line** | A pre-registered experiment measuring when LLM-generated SQL is safe to trust |
| **Live report** | https://a28-2001.github.io/yardstick/ |
| **Code and data** | https://github.com/A28-2001/yardstick |
| **Author** | Aakash Mehta |
| **Date** | July 2026 |
| **Type** | Solo, self-directed. Not employment or coursework. |
| **Status** | Complete and published |

---

## What it is

Teams increasingly let language models write SQL against production databases. The normal
process is to validate on a benchmark, pick the prompt that scores best, and deploy it
everywhere. This project ran a controlled experiment to test whether that is safe.

**Design:** a 2x2 factorial, prompt strategy (zero-shot vs few-shot) crossed with model
size (Llama-3.1-8B vs Llama-3.3-70B), run across three query-complexity tiers. 150
natural-language questions, 600 generated queries, every one executed against a real
SQLite database and compared to a human-written gold answer.

**The methodological point:** the hypothesis, the primary metric and the statistical test
were written into `PREREGISTRATION.md` and committed to Git **before** the full run. The
commit timestamp is in the public history. This matters because a 10-question pilot had
suggested few-shot prompting nearly doubled accuracy on hard queries; at the full sample
that collapsed to nothing. Pre-registration is why it is reported as a null result rather
than a discovery.

---

## Scale and rigour metrics

- 150 questions across 93 databases, drawn from Spider (Yale LILY, CC BY-SA 4.0)
- 600-cell complete counterfactual matrix (every variant ran on every question)
- 680 successful API calls, 0 extraction failures, 0 execution timeouts
- Total cost **$0.00 actual** (free tier), $0.19 at published list prices
- Scorer cross-validated against the official Spider evaluation script: **18/19 agreement (95%)**
- 82 files, ~25 commits, fully reproducible from committed CSVs

---

## Findings (all final, all in the public report)

**1. Prompt engineering did nothing measurable.** Few-shot vs zero-shot lift was
-2 pts (simple), 0 pts (moderate), +8 pts (complex). All non-significant after
Benjamini-Hochberg correction (adjusted p ~ 1.0). A pre-registered null result.

**2. Model size was the only lever that moved anything, and only on hard queries.**
8B to 70B gave **+28 points on complex queries** (95% CI [+14, +42], p = 0.0013)
zero-shot, +16 points (p = 0.039) few-shot, and **exactly zero** on the middle tier.

**3. The headline: better models fail more quietly.** The most accurate configuration
made the fewest errors, and **100% of them were silent**: they executed without error and
returned plausible wrong numbers. Both large-model variants were 95% and 100% silent
against 81% and 89% for the small ones. Across tiers, 82 to 97% of all errors were silent.
Implication: choosing a model on benchmark score selects for quieter failures.

**4. Self-reported confidence is close to useless; cross-model agreement works.** Every
variant was overconfident (weakest: claims 98.6% confidence, is 76.7% correct, ECE 0.219).
For predicting correctness, cross-model result agreement scored **AUC 0.861** against
**0.647** for the model's own confidence. This yields a deployable rule: run two cheap
models, compare executed results, review the 28% where they disagree, and catch **84% of
all errors at a 16% false-alarm rate**.

**5. Difficulty routing failed, reported as a negative result.** A 6-feature difficulty
predictor (AUC 0.665) was **beaten by question length alone** (0.724). Routing retained
88.7% of the expensive model's accuracy at 28% of its cost, but **random routing at the
same budget matched it exactly**. A secondary finding: cost and difficulty are decoupled,
since question length predicts difficulty while schema size predicts cost (r = 0.95) and
difficulty not at all.

---

## What was engineered

**Data pipeline.** Downloads and validates the Spider benchmark. Every gold query is
executed before its question enters the sample; 7 returning zero rows were excluded, and
hand review of 20 questions found and excluded 2 with genuinely broken ground truth (a
join condition comparing a column to itself, producing a silent cartesian product).

**Generation infrastructure.** Hash-cached and resumable: writes to Postgres after every
call, so hitting the free tier's 100,000-tokens-per-day ceiling mid-run costs nothing.
The full run legitimately spanned several days because of that ceiling and completed with
zero re-spend. Exponential backoff on transient errors, fail-fast on daily caps.

**Execution sandbox.** Generated SQL is untrusted, so every query runs against a
read-only copy of the database with a 30-second timeout and a 10,000-row cap. The row cap
fired in practice on a runaway join.

**Separation of concerns.** Generation and scoring are separate stages with results
stored independently, so a fix to the comparison logic can be re-scored across all 600
cells at zero API cost. This was used repeatedly.

**Scoring.** Result-set canonicalisation and hashing with documented comparison rules
(order-insensitive, duplicates preserved, floats rounded). A single-bucket error taxonomy
via `sqlglot` AST comparison, classifying failures as wrong join, wrong filter, wrong
projection, wrong aggregation or schema error.

**Statistics, hand-built.** McNemar's exact test for paired binary outcomes (a paired
t-test on binary data is the standard mistake and was avoided), 10,000-resample bootstrap
confidence intervals resampling questions to preserve pairing, Benjamini-Hochberg FDR
across the pre-registered comparisons, a power analysis fixing the minimum detectable
effect, and a difference-in-differences contrast for the 2x2 interaction.

**Machine learning.** Difficulty prediction from 15 features computed from question text
and schema alone, with an explicit code-level constraint that no feature may derive from
the gold SQL (which does not exist at inference time). Validated with leave-one-tier-out
and leave-one-database-out cross-validation across 93 folds, benchmarked against three
mandatory baselines, and checked against an oracle upper bound.

**Reporting.** Five matplotlib figures in a custom style, regenerable from committed CSVs
with no database access. A published web report with a sticky contents rail, real
captured terminal output, and a print stylesheet.

---

## Technical stack

Python 3.11 · SQL / SQLite / PostgreSQL (Supabase) · statsmodels · scikit-learn · pandas ·
NumPy · SciPy · sqlglot · matplotlib · Groq API (Llama 3.1 8B, Llama 3.3 70B) · Git ·
GitHub Pages · HTML/CSS

Deliberately **not** used: LangChain, Ragas, DeepEval or any prebuilt evaluation
framework. The statistical layer is hand-built, which was the point of the exercise.

---

## Skills this evidences

- Experimental design: factorial designs, pre-registration, power analysis, control of confounds
- Applied statistics: paired hypothesis testing, bootstrap inference, multiple-comparison correction, calibration (ECE), ROC/AUC
- Data engineering: idempotent and resumable pipelines, caching, rate-limit handling, relational schema design
- SQL: query semantics, AST analysis, execution-based correctness, join reasoning
- Machine learning: feature engineering under a leakage constraint, logistic regression, grouped cross-validation, baseline discipline
- Data visualisation: custom matplotlib figure design
- LLM engineering: prompt configuration, structured output extraction, cost and token accounting, confidence calibration
- Technical writing: a research report written for a mixed technical and non-technical audience

---

## Honest framing notes for whoever writes the resume

Please respect these; overstating undermines the thing that makes the project credible.

1. **Two of the three research questions produced null or negative results.** That is the
   project's strength, not a weakness, but it must not be written as a performance claim.
   Do **not** write "improved accuracy by X%" for the prompting or routing work. The
   honest framing is rigour and intellectual honesty: pre-registration prevented a false
   positive, and the negative routing result was published rather than buried.
2. **The +28 point model effect is a measured comparison between two models**, not an
   improvement the author engineered. Phrase it as "measured" or "quantified", not
   "achieved" or "delivered".
3. **Nothing was deployed to production.** The deployment recommendation is a conclusion
   drawn from the data, not a shipped system. Do not imply production usage or business impact.
4. **Sample size is 150 questions**, powered to detect roughly 14 to 27 percentage-point
   effects. Do not imply large-scale evaluation.
5. **Cost figures are list-price equivalents.** Actual spend was zero on a free tier.
   "$0.19" is a modelled number, not a bill.
6. **Known limitations, stated in the report:** benchmark contamination is possible since
   Spider is public; complexity is confounded with question length and schema size;
   single-instance execution accuracy admits spurious matches; both models are from one
   family, so the model effect means size within a family rather than a vendor comparison.

Strongest resume-worthy angles, in order: the **silent-failure finding** (counterintuitive
and genuinely useful), the **pre-registration discipline** (rare outside academia), the
**cross-model agreement result** (an actionable deployment rule with concrete numbers),
and the **hand-built statistical layer** (depth rather than framework glue).
