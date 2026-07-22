# Yardstick

**A statistically rigorous evaluation and routing study for LLM-generated SQL.**

---

## 0. Read this first

This document is the complete build specification, written to be executed phase by phase.

Two rules govern every decision below:

1. **The deliverable is a study with findings, not a product.** No UI. No chat interface. No general-purpose framework. A reader should open the README, understand the question, see the evidence, and act on the recommendation.
2. **A null result is a legitimate outcome.** If variants do not differ significantly, that is a finding and it gets reported as one. Do not p-hack toward a story.

---

## 1. The research question

Teams are increasingly letting LLMs write SQL against production warehouses. Most validate on a benchmark, pick the winning prompt, and deploy it uniformly.

**This study asks whether that is safe, and where it stops being safe.**

> Does the effectiveness of prompt engineering for text-to-SQL depend on query complexity, and if so, can that difficulty be predicted from the question and schema alone, before generating any SQL, and used to route cost-effectively?

- **RQ1 (lift).** Does few-shot prompting improve execution accuracy, and does the size of that improvement differ across query complexity tiers?
- **RQ2 (routing).** Can question difficulty be predicted from cheap, LLM-free features and used to route to the appropriate model?
- **RQ3 (calibration).** Does self-reported confidence predict correctness, and does cross-variant agreement predict it better?

**The stakes framing, for the README:** a SQL query that throws a syntax error is a visible failure. A query that executes cleanly and returns plausible but wrong numbers is an invisible one. The second is far more dangerous, and this study measures how often it happens.

---

## 2. Positioning

Not an LLM evaluation framework. Braintrust, LangSmith, Ragas, and DeepEval already do model comparison. Spider and BIRD already publish leaderboards.

What is uncommon here:

- Statistical rigor applied to prompt decisions: power analysis, paired testing, bootstrap intervals, multiple comparison correction, pre-registration
- Complexity-tier generalization rather than a single aggregate benchmark score
- A prospective difficulty predictor enabling cost-based routing, validated against human difficulty labels
- Calibration analysis focused on the silent-failure mode
- A deployment recommendation with a cost tradeoff as the output, not a leaderboard position

**One-line pitch:**
> Most teams pick one model and prompt for all SQL generation. Yardstick predicts which questions are hard before generating anything, routes accordingly, and quantifies both what that saves and where silent failures concentrate.

---

## 3. Constraints

**Everything must be free.** Verify current free tier terms on day one, they change.

| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| LLM primary | Groq | Free tier, main workhorse |
| LLM comparison | Anthropic Claude API | Small credit, final run only |
| LLM third (optional) | Google Gemini API | Adds a third model if budget allows |
| Results database | Supabase Postgres | Free tier. Strongly preferred over local, see 13.4 |
| Target databases | SQLite | Spider ships SQLite databases. Execute locally |
| SQL parsing | sqlglot | For AST-level analysis and error classification |
| Statistics | SciPy, statsmodels | |
| Data | pandas, numpy | |
| ML | scikit-learn | Logistic regression and shallow trees only |
| Visualization | Looker Studio | Free, closes a real skills gap |
| Orchestration | GitHub Actions | 2,000 free minutes per month |
| Dev | Claude Code, Cursor | |

**Do not use** LangChain, Ragas, DeepEval, or any prebuilt eval library. Building the statistical layer by hand is the entire point. Importing someone else's harness produces a wrapper, not a skill.

**One exception worth making:** use the official Spider evaluation script as a cross-check against your own execution-accuracy implementation. If they disagree, you have a bug. Do not use it as your primary scorer, write your own, but validate against it.

---

## 4. Experimental design

### 4.1 Factorial structure

A **2 x 2 factorial design**, run across three complexity tiers.

| Factor | Levels |
|---|---|
| Prompt strategy | zero-shot, few-shot |
| Model | Groq (cheap), Claude (expensive) |

| ID | Prompt | Model | Role |
|---|---|---|---|
| V1 | zero-shot | Groq | baseline, cheapest |
| V2 | few-shot | Groq | prompt effect, cheap |
| V3 | zero-shot | Claude | model effect, expensive |
| V4 | few-shot | Claude | both, most expensive |

A 2x2 decomposes prompt effect, model effect, and interaction. **Do not add variants.** Scope discipline is what makes this finishable.

### 4.2 Complexity tiers

| Tier | Definition | Target n |
|---|---|---|
| Simple | Single table, SELECT with WHERE, no joins, no aggregation | 50 |
| Moderate | 2 to 3 joins, GROUP BY, aggregate functions | 50 |
| Complex | Nested subqueries, 4+ joins, set operations, HAVING, window functions | 50 |

**Total: 150 questions. 150 x 4 variants = 600 API calls.**

### 4.3 Tier assignment, and why this is a strength

Spider ships with **human-assigned difficulty labels** (easy, medium, hard, extra-hard) derived from SQL structural complexity.

Use those labels to define your tiers rather than inventing your own. Two benefits:

1. **Tier assignment is externally validated**, not your own subjective judgment. A reviewer cannot accuse you of drawing the boundaries to fit your conclusion.
2. **You get a free validation target for the difficulty predictor.** In Phase 8, check whether your cheap-feature model recovers the human difficulty label. If it does, that is a stronger claim than "my model predicts my own metric."

Map Spider's four labels onto three tiers: easy → Simple, medium → Moderate, hard + extra-hard → Complex. Document the mapping.

### 4.4 The comparability question

Unlike the document version of this design, **execution accuracy IS comparable across tiers.** A correct query is a correct query regardless of complexity. This is a genuine simplification.

However, the **primary analysis is still relative lift within tier**, because that is what the research question asks. Absolute accuracy across tiers is reported as descriptive context, not as the hypothesis test.

### 4.5 Acknowledged confounds

State these plainly in limitations. Do not hide them.

**Confound 1: complexity correlates with question length and schema size.** Complex queries tend to come from larger databases and longer questions. You cannot fully separate "complexity effect" from "context length effect."
- *Partial mitigation:* within the Complex tier, sample across a range of schema sizes rather than taking the largest databases only.

**Confound 2: database diversity.** Spider spans 200 databases with wildly different schemas. Sampling 150 questions means uneven database representation.
- *Mitigation:* cap questions per database at 3, so no single schema dominates a tier. Record `db_id` and report the distribution.

**Confound 3: Spider is a benchmark, and models may have seen it in training.** This is a real and unavoidable limitation for any public benchmark.
- *Mitigation:* state it explicitly. Optionally run a small held-out check using BIRD or a hand-written question set against the same schemas, and report whether relative rankings hold. If they do, contamination affects absolute scores but not your comparative conclusion, which is what the study is actually about.

**Confound 3 is the one an informed reviewer will raise.** Having the answer ready is a credential.

---

## 5. Pre-registration

**Complete and commit to Git BEFORE running the full experiment.** Timestamped in commit history. This is what separates the project from post-hoc storytelling.

Create `PREREGISTRATION.md`:

```
## Primary hypothesis
H1: The execution-accuracy lift of few-shot prompting over zero-shot
    (V2 - V1) differs significantly across query complexity tiers.

## Primary metric
Execution accuracy: binary per question. 1 if the generated query
executes without error AND returns a result set matching the gold
query's result set under the comparison rules in section 9.2.
Otherwise 0.

## Primary comparison
V2 vs V1, within each complexity tier. Three comparisons total.

## Correction
Benjamini-Hochberg FDR correction applied to the three primary
comparisons only.

## Significance threshold
alpha = 0.05

## Sample size justification
[Insert power calculation output from Phase 4]

## Pre-specified secondary metric
Silent failure rate: proportion of generated queries that execute
successfully but return a non-matching result set. Reported per
variant per tier, uncorrected, labeled exploratory.

## Everything else is exploratory
Model effect (V3 vs V1), interaction (V4), query efficiency, routing
performance, calibration analysis, and error taxonomy are labeled
exploratory and reported without correction, with that status stated
explicitly.
```

**Why this matters:** 4 variants x 3 tiers x 3 metrics is 36 possible comparisons. Correcting all of them destroys statistical power. Pre-registering one primary comparison preserves power and is exactly what real experimentation teams do.

---

## 6. Data

### 6.1 Source

| Component | Dataset | Source | Notes |
|---|---|---|---|
| Primary | Spider | Hugging Face / Yale LILY | ~10,000 question-SQL pairs, 200 databases, SQLite files included |
| Contamination check (optional) | BIRD | Hugging Face | Newer, harder, messier schemas, includes efficiency dimension |

Verify current licensing and availability yourself. My information may be stale.

**Why Spider:** it ships the actual SQLite databases, which is essential. Without executable databases you cannot compute execution accuracy and the entire design collapses into string comparison, which is exactly what you moved away from.

### 6.2 Data handling rules

- **Never commit database files or raw dataset files to the repo.** Commit a download script instead. Spider's database bundle is large.
- **Verify every SQLite database opens and the gold query executes** before including a question in your sample. Some benchmark entries have broken gold queries. Silently including them poisons your ground truth.
- **Cap at 3 questions per database** so no schema dominates a tier.
- **Fixed random seed** for all sampling. Non-negotiable.
- **Store the schema DDL alongside each question** in the results database, so runs are reproducible without re-reading the SQLite files.

### 6.3 Ground truth validation

**This replaces the label-normalization day from the document version, and it is much lighter, but do not skip it.**

For all 150 sampled questions:

- [ ] Execute the gold SQL against its database. Confirm it runs without error.
- [ ] Confirm it returns a non-empty result set. Empty gold results make execution comparison degenerate, since a broken query returning empty would score as correct. **Exclude questions whose gold query returns zero rows**, and log how many you excluded.
- [ ] Confirm the question text is unambiguous. Hand-read 20 of them. Spider contains some genuinely ambiguous questions where multiple correct SQL formulations exist with different result sets.
- [ ] Record `db_id`, gold SQL, gold result set hash, row count, and column count.

**Hand-verify 20 examples.** Mandatory. If your ground truth is wrong, every downstream statistic measures the error, not the model.

---

## 7. Database schema

Results go in Supabase Postgres. Target databases stay as local SQLite files.

```sql
CREATE TABLE questions (
    question_id         TEXT PRIMARY KEY,
    db_id               TEXT NOT NULL,
    question_text       TEXT NOT NULL,
    gold_sql            TEXT NOT NULL,
    gold_result_hash    TEXT NOT NULL,
    gold_row_count      INTEGER NOT NULL,
    gold_col_count      INTEGER NOT NULL,
    spider_difficulty   TEXT NOT NULL,     -- easy, medium, hard, extra
    tier                TEXT NOT NULL,     -- simple, moderate, complex
    schema_ddl          TEXT NOT NULL,
    split               TEXT NOT NULL,     -- train or test
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE variants (
    variant_id          TEXT PRIMARY KEY,  -- V1, V2, V3, V4
    prompt_strategy     TEXT NOT NULL,     -- zero-shot, few-shot
    model               TEXT NOT NULL,     -- groq, claude
    prompt_version      TEXT NOT NULL,     -- git hash or semver
    config_path         TEXT NOT NULL
);

CREATE TABLE runs (
    run_id              BIGSERIAL PRIMARY KEY,
    question_id         TEXT REFERENCES questions(question_id),
    variant_id          TEXT REFERENCES variants(variant_id),
    replicate           INTEGER DEFAULT 1,
    raw_output          TEXT NOT NULL,     -- full model response, ALWAYS store
    extracted_sql       TEXT,              -- null if extraction failed
    extraction_success  BOOLEAN NOT NULL,
    self_confidence     NUMERIC,
    input_tokens        INTEGER NOT NULL,
    output_tokens       INTEGER NOT NULL,
    cost_usd            NUMERIC NOT NULL,
    latency_ms          INTEGER NOT NULL,
    temperature         NUMERIC NOT NULL,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (question_id, variant_id, replicate)
);

CREATE TABLE executions (
    execution_id            BIGSERIAL PRIMARY KEY,
    run_id                  BIGINT REFERENCES runs(run_id) UNIQUE,
    executed                BOOLEAN NOT NULL,       -- did it run at all
    execution_error         TEXT,
    result_hash             TEXT,
    result_row_count        INTEGER,
    result_col_count        INTEGER,
    exact_match             BOOLEAN,                -- ordered comparison
    set_match               BOOLEAN,                -- THE primary correctness flag
    execution_time_ms       NUMERIC,
    timed_out               BOOLEAN NOT NULL DEFAULT false,
    error_type              TEXT                    -- see 9.5 taxonomy
);

CREATE TABLE question_features (
    question_id             TEXT PRIMARY KEY REFERENCES questions(question_id),
    question_token_count    INTEGER,
    question_char_count     INTEGER,
    schema_table_count      INTEGER,
    schema_column_count     INTEGER,
    schema_ddl_token_count  INTEGER,
    question_entity_count   INTEGER,
    has_superlative         BOOLEAN,
    has_comparison          BOOLEAN,
    has_aggregation_cue     BOOLEAN,
    has_temporal_cue        BOOLEAN,
    has_negation            BOOLEAN,
    clause_count            INTEGER,
    numeric_mention_count   INTEGER
);
```

**Three critical points:**

1. **`runs.raw_output` stores the unparsed response.** This lets you re-extract and re-score later without re-spending tokens. The single most regretted omission if skipped.
2. **`executions` is separate from `runs`** because execution is a distinct, re-runnable step. If you fix a bug in your comparison logic, you re-run executions against stored SQL, at zero API cost.
3. **`set_match` is the primary correctness flag.** See 9.2 for why it is set-based rather than exact.

---

## 8. Caching and execution infrastructure

### 8.1 Generation cache

**Build this before any experiment code.** Highest-leverage token saver in the project.

Cache key: `sha256(question_id + variant_id + prompt_version + model + temperature + replicate)`

1. Compute hash
2. Query `runs` for that key
3. If present, return cached, zero API cost
4. If absent, call, write to Postgres immediately, return

**Write to Postgres after every single call, never batch at the end.** Rate limits will interrupt a long run, and losing 140 questions of progress is entirely avoidable.

Also implement:
- Exponential backoff on 429 responses, starting at 2 seconds, max 60 seconds, 5 retries
- Resumable run mode that skips already-completed cells

### 8.2 SQL execution sandbox

**This is new relative to the document version and it needs real care.**

Generated SQL is untrusted input. Even without malice, an LLM can produce a query that hangs.

Mandatory safeguards:

- [ ] **Open every SQLite database read-only.** Use `file:path?mode=ro` URI. Prevents any write, drop, or alter from corrupting ground truth.
- [ ] **Set a hard execution timeout of 30 seconds.** Use SQLite's `set_progress_handler` or run in a subprocess with a kill timer. A cartesian join on a large table will otherwise hang the run.
- [ ] **Cap returned rows at 10,000.** A runaway query returning millions of rows will exhaust memory.
- [ ] **Work on a copy of each database**, not the original download, so any accidental mutation is recoverable.
- [ ] **Catch and classify every exception.** Never let an execution error crash the run loop.
- [ ] **Log `timed_out` separately from `execution_error`.** A timeout is a different failure mode than a syntax error and belongs in its own taxonomy bucket.

### 8.3 SQL extraction from model output

Models wrap SQL in markdown fences, add explanations, or emit multiple statements.

Extraction rules, applied in order:
1. If a ```sql fenced block exists, take the first one
2. Else if a generic ``` fenced block exists, take the first one
3. Else take the text from the first `SELECT` or `WITH` keyword to the end
4. Strip trailing semicolons and whitespace
5. If more than one statement is present, take the first and log it

**Rule decided in advance: extraction failure scores 0, it is not retried.** Log `extraction_success = false` and report the rate per variant. An LLM that cannot reliably emit parseable SQL is a real production problem and hiding it inflates your results.

---

## 9. Scoring

### 9.1 Why this section is short

In the document-extraction version, scoring required normalization rules, fuzzy matching, field-level F1, and an LLM judge. **None of that is needed here.** Correctness is determined by executing two queries and comparing result sets. This is the main reason the SQL substrate is the better choice.

### 9.2 Execution accuracy, the primary metric

Binary per question, per variant.

**Procedure:**
1. Extract SQL from the model output
2. Execute against the read-only database copy with timeout
3. Execute the gold SQL against the same database
4. Compare result sets

**Comparison rules, and these must be documented in the README:**

| Rule | Decision | Rationale |
|---|---|---|
| Row order | **Ignored** unless the gold query contains `ORDER BY` | A correct answer should not fail because rows came back in a different order |
| Column order | **Ignored.** Compare as multisets of value tuples, sorted within each row | Column aliasing and ordering vary legitimately |
| Column names | **Ignored** | `COUNT(*)` vs `total` is not a correctness difference |
| Duplicate rows | **Preserved.** Compare as multisets, not sets | `DISTINCT` versus not is a real semantic difference |
| Numeric tolerance | Round floats to 4 decimal places before comparison | Floating point representation should not cause false failures |
| NULL handling | `NULL` equals `NULL` for comparison purposes | |
| Empty result sets | Excluded at sampling time (see 6.3) | Prevents degenerate matching |

Implement as: canonicalize each result set to a sorted list of sorted tuples with rounded floats, hash it, compare hashes. Store the hash in `executions.result_hash`.

**Record both `exact_match` (order-sensitive) and `set_match` (order-insensitive).** `set_match` is the primary metric. Reporting the gap between them is informative, it tells you how often models get the right data in the wrong order.

### 9.3 Cross-validation against the official scorer

Run the official Spider evaluation script on a 30-question subset and compare its verdicts to yours.

**If they disagree on any question, investigate before proceeding.** Either your comparison logic has a bug or you have found a legitimate edge case worth documenting. Both outcomes are valuable, and doing this check is itself a credibility signal.

### 9.4 The silent failure rate, your best secondary metric

**Pre-specified in the pre-registration. This is the most interesting number in the study.**

```
silent_failure_rate = count(executed = true AND set_match = false) / count(all questions)
```

A query that throws an error is a visible failure, the analyst notices and investigates. A query that executes cleanly and returns plausible but wrong numbers is invisible, and it flows into a dashboard or a decision.

Report this per variant per tier. The likely and most quotable finding is that **the more capable model produces fewer total errors but a higher proportion of silent ones**, because weaker models fail loudly with syntax errors while stronger models fail quietly with subtly wrong joins.

If that pattern holds, it is the single strongest result in the project.

### 9.5 Error taxonomy

Classify every failure into exactly one type. Use `sqlglot` to parse the generated SQL for structural classification.

| Type | Definition | Detection |
|---|---|---|
| `extraction_failure` | No parseable SQL in the model output | Extraction step failed |
| `syntax_error` | SQL does not parse or execute | Execution raised a syntax exception |
| `schema_error` | References a nonexistent table or column | Execution error mentions unknown table/column, or AST check against DDL |
| `timeout` | Exceeded 30 second limit | Timeout flag |
| `wrong_join` | Executes, wrong result, join structure differs from gold | AST comparison of FROM/JOIN clauses |
| `wrong_aggregation` | Executes, wrong result, GROUP BY or aggregate function differs | AST comparison of GROUP BY/aggregates |
| `wrong_filter` | Executes, wrong result, WHERE/HAVING differs | AST comparison of predicates |
| `wrong_projection` | Executes, wrong result, selected columns differ | AST comparison of SELECT list |
| `semantically_different` | Executes, wrong result, no single structural difference isolated | Fallback bucket |

**Classification order matters.** Check in the sequence listed above, assign the first match, so each failure lands in exactly one bucket.

Reporting a taxonomy instead of one accuracy number demonstrates analytical depth, and the join versus aggregation split is genuinely diagnostic. It tells a reader *what kind of reasoning* the model is failing at.

### 9.6 Query efficiency, exploratory

For queries that are **correct** (`set_match = true`), record `execution_time_ms`.

Compare median execution time across variants within tier. Two queries can both be correct while one is dramatically slower.

**Potential finding:** "Variant B is equally accurate but generates queries with 3x higher median execution time." In a production warehouse where compute is billed per query, that is a real cost that never appears on an accuracy leaderboard.

Caveat honestly: SQLite execution time on small benchmark databases is a weak proxy for warehouse performance. State that. Optionally supplement with a static complexity proxy from the AST, join count, subquery depth, presence of full scans.

### 9.7 What is deliberately not here

**No LLM-as-judge.** Correctness is objective. This removes the judge-bias risk, the judge-validation requirement, and roughly 6 hours of work. Do not reintroduce it.

---

## 10. Statistical methods

### 10.1 Distributional considerations

**Important difference from the document version.** Execution accuracy is **binary per question**, not a continuous F1 score. That changes the appropriate tests.

Per variant per tier you have a proportion. Per question you have a paired binary outcome across variants.

**For the primary comparison (V2 vs V1 within tier), use McNemar's test.** It is the correct test for paired binary outcomes. It looks only at discordant pairs: questions where one variant succeeded and the other failed.

```python
from statsmodels.stats.contingency_tables import mcnemar
# table = [[both_correct, v1_only], [v2_only, both_wrong]]
result = mcnemar(table, exact=True)
```

Use the exact binomial version, not the chi-square approximation, since discordant counts will be small at n=50.

**Do not use a paired t-test on binary data.** This is the most likely statistical error in this version of the project.

### 10.2 Confidence intervals

**Bootstrap the difference in proportions.** 10,000 resamples, percentile method, resampling questions (not observations) to preserve the pairing.

Report the CI on the accuracy difference in percentage points. A CI that crosses zero means you cannot distinguish the variants, and you say so plainly.

### 10.3 Power analysis

**Run in Phase 4, before the full experiment, using pilot-observed proportions.**

For paired binary data, power depends on the discordant proportion, not just the marginal accuracies.

```python
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

effect = proportion_effectsize(p_treatment, p_control)  # from pilot
n_required = NormalIndPower().solve_power(
    effect_size=effect,
    alpha=0.05,
    power=0.80,
    alternative='two-sided'
)
```

This gives a conservative estimate. The paired design will need fewer, which you can note.

**If n_required substantially exceeds 50 per tier**, you have two honest options:
1. Accept that you can only detect large effects, and **state the minimum detectable effect explicitly in the README**
2. Increase sample size per tier

**Do not run the full experiment without doing this.** Discovering an experiment was underpowered afterward would be embarrassing in a project about experimentation.

### 10.4 Multiple comparison correction

Apply **Benjamini-Hochberg FDR** to the three primary comparisons only (V2 vs V1, within each tier).

Exploratory analyses reported uncorrected, with that status stated explicitly in the results section.

### 10.5 Ceiling and floor effects

**Check both in the pilot. This version is more vulnerable than the document version.**

- **Ceiling:** if all variants exceed roughly 92% on the Simple tier, there is no room to detect a difference. Likely, since simple single-table queries are close to solved.
- **Floor:** if all variants fall below roughly 15% on the Complex tier, the same problem in reverse.

**Mitigation if the Simple tier ceilings:** this is itself a legitimate finding. Report it as "prompt strategy is irrelevant on simple queries because all variants saturate," and let the interesting comparison live in Moderate and Complex. Do not force a difference that is not there. But adjust the pre-registration *before* the full run if you drop a tier from the primary hypothesis, and note the change with its timestamp.

### 10.6 Effect size versus significance

Report both. A 2 percentage point improvement can be statistically significant and operationally worthless.

The recommendation column in the final report is driven by **effect size and cost**, not by p-value alone.

---

## 11. Routing and difficulty prediction

### 11.1 The counterfactual matrix

Because every variant runs on every question, you have a complete counterfactual matrix: for each question, the correctness, cost, and latency of every possible routing decision.

**Routing simulation costs zero additional API calls.** You are selecting cells from a table you already have.

### 11.2 Avoiding circularity

**Split before anything else.** Before feature engineering, before predictor training, before any routing evaluation.

- Train: 60% of questions, stratified by tier and by `db_id` where possible
- Test: 40%, same stratification

Train the difficulty predictor on train only. Simulate and report routing performance on test only.

**Additionally: leave-one-tier-out validation.** Train on Simple and Moderate, test routing on Complex. If it holds, you have a genuine generalization claim. If it does not, report that honestly, it is still a finding, and arguably a more interesting one.

**And a stronger check available here that was not available in the document version: leave-one-database-out.** Train on questions from databases A through N, test on questions from unseen databases. This tests whether difficulty prediction transfers to schemas the model has never seen, which is the actual production question.

### 11.3 Features

**Hard constraint: every feature must be computable from the question text and schema DDL alone, without generating any SQL and without an LLM call.** If a feature requires calling a model, routing is pointless, you already paid the cost you were avoiding.

**Question features:**

| Feature | Rationale |
|---|---|
| `question_token_count` | Length proxy |
| `question_char_count` | Length proxy |
| `question_entity_count` | Count of quoted strings, proper nouns, capitalized tokens |
| `has_superlative` | Regex for most, least, highest, lowest, top, best, maximum, minimum. Implies ORDER BY or window functions |
| `has_comparison` | Regex for more than, less than, at least, between, greater. Implies complex predicates |
| `has_aggregation_cue` | Regex for total, average, sum, count, number of, per, each. Implies GROUP BY |
| `has_temporal_cue` | Regex for date, year, month, before, after, since, during. Date reasoning is a known failure mode |
| `has_negation` | Regex for not, never, without, excluding. Negation is disproportionately error-prone |
| `clause_count` | Count of and, or, but, that, which. Compound conditions |
| `numeric_mention_count` | Count of numeric literals in the question |

**Schema features:**

| Feature | Rationale |
|---|---|
| `schema_table_count` | Search space size |
| `schema_column_count` | Search space size |
| `schema_ddl_token_count` | Context burden |
| `foreign_key_count` | Join complexity potential |
| `max_table_column_count` | Widest table, projection difficulty |

**Do not include any feature derived from the gold SQL.** That is leakage, and it is the most likely way to accidentally invalidate the routing result. The gold query is not available at inference time in production, so it cannot be a feature. Write this constraint into a code comment where features are computed.

### 11.4 Model choice

**150 questions is far too small for gradient boosting. Do not use it.**

Use **logistic regression** predicting binary hard/easy, or a **shallow decision tree** with `max_depth` of 3 to 4. Four to six features maximum.

**Three mandatory baselines you must beat, or honestly report that you did not:**

1. **Question length only.** A single feature, `question_token_count`.
2. **Schema size only.** A single feature, `schema_table_count`.
3. **Random routing** at the same cheap/expensive split rate.

If the length-only baseline matches your multi-feature model, **report that**. "The simplest possible feature captures most of the signal" is a legitimate and interesting finding, and reporting it costs nothing while inventing complexity to avoid it costs credibility.

### 11.5 Validation against human difficulty labels

**This is available here and it was not available in the document version. Use it.**

Spider's human-assigned difficulty labels give you an external validation target.

Check: does your feature-based predictor recover the human difficulty label? Report accuracy, and a confusion matrix.

If yes, your claim strengthens considerably: *"question difficulty is predictable from surface features alone, validated against independent human annotations, not just against my own outcome metric."*

If no, that is also interesting: *"human-perceived SQL difficulty is not recoverable from surface features, meaning routing must be trained on outcomes rather than on intuition."*

Either result is publishable within the study.

### 11.6 Routing policies to compare

Simulate all six on the test set:

| Policy | Description |
|---|---|
| `always_cheap` | V1 or V2 on everything |
| `always_expensive` | V3 or V4 on everything |
| `random` | Coin flip at matched split rate, null baseline |
| `length_only` | Baseline predictor, single feature |
| `difficulty_routed` | Your full predictor |
| `oracle` | Perfect foresight, upper bound |

**The oracle bound is the most valuable comparison.** It tells you what fraction of the theoretical maximum your router captured. "Difficulty routing captured 78% of the oracle's available savings" is far more honest and more interesting than a raw savings number in isolation.

### 11.7 Reported outcome

For each policy on the test set:
- Execution accuracy
- Total cost in USD
- Accuracy retained versus always-expensive, as a percentage
- Cost relative to always-expensive, as a percentage
- Fraction of oracle savings captured

Headline claim format:
> Difficulty-aware routing achieved X% of the always-expensive policy's execution accuracy at Y% of its cost, capturing Z% of the oracle upper bound, and outperforming a length-only baseline by W points.

**Include the routing threshold sensitivity.** Sweep the routing threshold from 0 to 1 and plot the resulting accuracy-cost curve. A single operating point is a claim, a curve is an analysis.

---

## 12. Calibration analysis

### 12.1 The risk, and the reframe

Self-reported LLM confidence is often nearly uninformative. If it turns out to be noise, an unplanned section dies.

**Reframe: you are testing whether confidence is useful, not assuming it.** Every outcome is a result. That framing removes the risk entirely.

### 12.2 Self-reported confidence

Request a confidence value from 0.0 to 1.0 alongside every generated query. Store in `runs.self_confidence`.

Analysis:
- Bin predictions into 10 confidence buckets
- Plot observed execution accuracy per bucket against stated confidence
- Compute **Expected Calibration Error (ECE)**
- Plot the reliability curve with the diagonal reference line

If poorly calibrated, that is the finding:
> Teams gating LLM-generated SQL on self-reported confidence are building on sand. Here is the evidence.

### 12.3 Cross-variant agreement as an alternative signal

**Costs nothing extra, you already have all four outputs per question.**

For each question, compute agreement across the four variants. Two useful definitions, compute both:

1. **Result-set agreement.** Fraction of variant pairs whose executed result sets match each other, regardless of whether they match gold. This is available at inference time in production, since you do not need the gold answer to notice that two models disagree.
2. **AST agreement.** Structural similarity of the generated queries via `sqlglot`.

Then test: does disagreement predict incorrectness better than self-reported confidence does?

Compare both signals by AUC for predicting `set_match`. If agreement wins, that is a sharper and more practically useful finding than either alone, and it maps to a real deployment pattern: run two cheap models, and escalate to human review only when they disagree.

**This is the strongest practical recommendation the study can produce.** Quantify it: what fraction of errors would be caught by flagging disagreement, and at what cost in false alarms?

### 12.4 The counterintuitive result to watch for

Two patterns worth checking explicitly, both of which invert common intuition:

1. **A more accurate variant that is more overconfident on its errors.** Higher mean stated confidence on incorrect queries than the weaker variant. This makes it more dangerous in an auto-execute workflow despite the better headline accuracy.
2. **A more accurate variant with a higher silent failure rate**, from section 9.4. Fewer total errors, but a larger share of them execute cleanly and return wrong numbers.

If either holds, it is the most quotable result in the project, because it means "pick the model with the highest benchmark score" is the wrong deployment heuristic.

---

## 13. Token, cost, and runtime management

Ranked by savings.

| Tactic | Impact | Implementation |
|---|---|---|
| Hash-based generation caching | Massive | Build first, Phase 2. Reruns cost zero |
| Separate execution from generation | Massive | Re-scoring after a comparison-logic bug costs zero API calls |
| 10-question pilot | Huge | Catches prompt bugs, ceiling effects, extraction failures before full spend |
| Groq as primary | Huge | Free tier. Claude reserved for the final comparison |
| Tight `max_tokens` | Large | SQL outputs are short. Cap at 400 to 600 |
| Prompt caching for few-shot | Large | Few-shot examples are identical across all questions in a tier |
| Schema truncation | Large | For very wide schemas, include only table and column names, not full DDL with constraints. Hold constant across variants |
| Anthropic Batch API | ~50% | Non-urgent runs. Ideal for this workload |
| Temperature 0 | Moderate | Fewer malformed outputs, fewer wasted retries |

### 13.1 Replicates

At temperature 0, output is near-deterministic.

**Run 3 replicates on the 10-question pilot only.** Measure variance in execution accuracy. If negligible, drop to 1 replicate for the full run **and document that decision explicitly in the methods section.**

This alone cuts token spend by roughly two thirds and is a legitimate, defensible methodological choice.

### 13.2 Schema presentation, held constant

Schemas must be included in every prompt. Decide **now** and write it down:

**Schema formatting is held constant across all variants, not tested.** Use the same DDL representation for V1 through V4. Otherwise schema formatting becomes an uncontrolled confound that could account for your entire effect.

Recommended: `CREATE TABLE` statements with column names and types, foreign keys included, constraints and indexes stripped.

### 13.3 Cost accounting

Count input and output tokens **separately**, at each provider's actual published per-token rate, logged per call in `runs.cost_usd`.

**Do not estimate at the end from averages.** You will be wrong and someone will ask.

Note that schema inclusion makes input tokens dominate heavily here, far more than in the document version. Report the input/output split, it is relevant to the routing cost argument.

### 13.4 Looker Studio connection

Decide in Phase 0, not at hour 70.

Looker Studio connects cleanly to Supabase Postgres but is painful with a local database. Either use Supabase, or plan to export final result tables to Google Sheets and connect Looker Studio to that. Both work. Discovering the problem late wastes an evening.

---

## 14. Build phases

### Phase 0. Setup and verification. ~2 hours

- [ ] Verify current free tier terms: Groq rate limits, Gemini free tier, Anthropic credits, Supabase row limits, GitHub Actions minutes
- [ ] Create repo, initialize Git
- [ ] Set up Supabase project and apply `schema.sql`
- [ ] Create `requirements.txt` with **pinned versions**
- [ ] Set up `.env` for API keys, add to `.gitignore`
- [ ] Verify Spider licensing and download availability
- [ ] **Decide Looker Studio connection approach now** (see 13.4)

**Exit criteria:** database connects, one successful API call to each provider, one SQLite database opens read-only and executes a query.

---

### Phase 1. Data acquisition and ground truth validation. ~5 hours

*Note: this is meaningfully lighter than the document version, which needed a full day of label normalization.*

- [ ] Write `scripts/download_data.py`, streams and samples, never commits raw files
- [ ] Make read-only working copies of all needed SQLite databases
- [ ] Map Spider difficulty labels to your three tiers, document the mapping
- [ ] Sample 50 questions per tier with a fixed seed, capping at 3 per `db_id`
- [ ] **Execute every gold query.** Exclude any that error, and log how many
- [ ] **Exclude questions whose gold query returns zero rows.** Log the count
- [ ] Compute and store gold result hashes, row counts, column counts
- [ ] Extract and store schema DDL per question
- [ ] **Hand-read 20 questions** for ambiguity. Exclude genuinely ambiguous ones
- [ ] Load into `questions`
- [ ] Assign train/test split, stratified by tier and `db_id`, before anything else

**Exit criteria:** 150 validated questions in Postgres, all gold queries confirmed executable and non-empty, 20 hand-reviewed, splits assigned.

---

### Phase 2. Infrastructure. ~7 hours

- [ ] Hash-based generation cache
- [ ] API clients for Groq and Claude with exponential backoff
- [ ] Per-call token and cost logging
- [ ] Write to Postgres after every call, never batch
- [ ] Resumable run mode
- [ ] **SQL extraction logic** with the fallback chain from 8.3
- [ ] **Execution sandbox** with read-only mode, 30s timeout, 10,000 row cap, exception classification (8.2)
- [ ] Prompt configs as YAML, versioned in Git
- [ ] Four variants as configs, not code branches

**Exit criteria:** one question runs through one variant, SQL extracts, executes safely, result lands in `runs` and `executions`, and re-running costs zero.

---

### Phase 3. Scoring. ~5 hours

- [ ] Result-set canonicalization and hashing per 9.2
- [ ] `exact_match` and `set_match` computation
- [ ] Extraction failure handling per 8.3
- [ ] Error taxonomy classification per 9.5, using `sqlglot` for AST comparison
- [ ] Silent failure rate computation per 9.4
- [ ] Execution time capture per 9.6
- [ ] **Cross-validate against the official Spider evaluation script on 30 questions** per 9.3

**Exit criteria:** your scorer agrees with the official scorer on 30 questions, or you have documented and understood every disagreement.

---

### Phase 4. Pilot, power analysis, pre-registration. ~4 hours

**This phase exists to prevent a wasted full run. Do not skip any item.**

- [ ] Run 10 questions through all 4 variants, 3 replicates
- [ ] **Check ceiling effects on Simple tier.** Above ~92% for all variants means no detectable difference
- [ ] **Check floor effects on Complex tier.** Below ~15% for all variants is the same problem inverted
- [ ] Check extraction failure rate
- [ ] Check timeout rate
- [ ] Measure replicate variance, decide replicate count for the full run
- [ ] Compute observed proportions per tier
- [ ] **Run the power analysis** per 10.3
- [ ] Write `PREREGISTRATION.md` and **commit it with a timestamp**

**Exit criteria:** power calculated, pre-registration committed, ceiling and floor effects assessed, replicate decision documented.

---

### Phase 5. Single-tier full run. ~7 hours

**Forcing function. Do not skip.**

- [ ] Run the full pipeline on **one tier only**, 50 questions, 4 variants. Use Moderate, it is least likely to ceiling or floor
- [ ] Run the complete statistical analysis on that tier
- [ ] Confirm: extraction works at scale, execution sandbox is stable, McNemar's test runs, effect is detectable

**Exit criteria:** a real, analyzed result for one tier. If something is fundamentally broken, you have lost 7 hours instead of 30.

---

### Phase 6. Full experiment. ~4 hours runtime, mostly unattended

- [ ] Run the remaining two tiers
- [ ] Monitor rate limits, extraction failures, and timeouts
- [ ] Verify all 600 cells present in `runs` and `executions`

**Exit criteria:** complete counterfactual matrix in the database.

---

### Phase 7. Primary statistical analysis. ~7 hours

- [ ] Build 2x2 contingency tables for V2 vs V1 within each tier
- [ ] **McNemar's exact test** per tier
- [ ] Bootstrap 95% CIs on the accuracy difference, 10,000 resamples
- [ ] Benjamini-Hochberg correction on the three primary comparisons
- [ ] Report effect sizes in percentage points alongside p-values
- [ ] **Silent failure rate per variant per tier**
- [ ] Error taxonomy breakdown per variant per tier
- [ ] Exploratory: model effect, interaction, query efficiency

**Exit criteria:** primary hypothesis answered with intervals and correction, silent failure rate computed.

---

### Phase 8. Difficulty prediction and routing. ~10 hours

- [ ] Compute all question and schema features, populate `question_features`
- [ ] **Verify no feature derives from gold SQL.** Code review this specifically
- [ ] Train logistic regression on train split only
- [ ] **Train all three baselines**: length-only, schema-size-only, random
- [ ] Leave-one-tier-out validation
- [ ] **Leave-one-database-out validation**
- [ ] **Validate predictor against Spider's human difficulty labels** per 11.5
- [ ] Simulate all six routing policies on the test split
- [ ] Compute the oracle upper bound
- [ ] **Sweep the routing threshold and plot the accuracy-cost curve**
- [ ] Report accuracy retained, cost saved, fraction of oracle captured, margin over baselines

**Exit criteria:** headline routing claim with three baselines, oracle bound, and a sensitivity curve.

---

### Phase 9. Calibration. ~6 hours

- [ ] Bin self-reported confidence, compute ECE, plot reliability curve
- [ ] Compute result-set agreement across variants per question
- [ ] Compute AST agreement via `sqlglot`
- [ ] Compare all three signals by AUC for predicting `set_match`
- [ ] **Quantify the practical recommendation**: what fraction of errors does disagreement-flagging catch, at what false alarm rate
- [ ] Check both counterintuitive patterns from 12.4

**Exit criteria:** calibration question answered either way, with a stated deployment recommendation.

---

### Phase 10. Reporting. ~8 hours

- [ ] Export result tables to Looker Studio via the approach decided in Phase 0
- [ ] Build five report pages: summary, lift by tier, silent failure analysis, routing frontier, error taxonomy
- [ ] Write the README as a research writeup, see section 16
- [ ] Write the limitations section honestly, including all three confounds from 4.5

**Exit criteria:** a reader can understand the question, the evidence, and the recommendation without asking you anything.

---

### Phase 11. Automation. ~4 hours. Build last

- [ ] GitHub Actions workflow triggering the eval suite on prompt config change
- [ ] Secrets management for API keys
- [ ] Regression check: flag if any variant's execution accuracy drops more than 2 points
- [ ] **Second regression check: flag if silent failure rate increases**, which is arguably the more important guard

**Exit criteria:** changing a prompt config triggers an automated evaluation run with both regression checks.

---

**Total estimate: 65 to 75 focused hours.** Slightly lighter than the document version, because scoring is objective and label normalization is largely replaced by validation.

---

## 15. Repository structure

```
yardstick/
├── README.md                      # The study writeup. The main deliverable
├── PREREGISTRATION.md             # Committed before Phase 5
├── LIMITATIONS.md                 # Or a section in README
├── requirements.txt               # Pinned versions
├── .env.example
├── .gitignore                     # Excludes data/, databases/, .env
│
├── configs/
│   ├── variants/
│   │   ├── v1_zeroshot_groq.yaml
│   │   ├── v2_fewshot_groq.yaml
│   │   ├── v3_zeroshot_claude.yaml
│   │   └── v4_fewshot_claude.yaml
│   └── schema_format.yaml         # Held constant across variants
│
├── scripts/
│   ├── download_data.py
│   ├── validate_gold.py           # Phase 1 ground truth validation
│   ├── run_experiment.py
│   ├── execute_and_score.py       # Separate from generation, re-runnable
│   ├── compute_features.py
│   ├── train_router.py
│   ├── simulate_routing.py
│   ├── analyze.py
│   └── crosscheck_official.py     # Validate scorer against Spider's
│
├── yardstick/
│   ├── cache.py                   # Hash-based generation caching
│   ├── clients.py                 # Groq, Claude, backoff
│   ├── extraction.py              # SQL extraction from model output
│   ├── sandbox.py                 # Read-only execution, timeout, row cap
│   ├── comparison.py              # Result-set canonicalization and matching
│   ├── taxonomy.py                # Error classification via sqlglot
│   ├── stats.py                   # McNemar, bootstrap, BH correction
│   ├── features.py                # Question and schema features
│   ├── routing.py                 # Policies, oracle, threshold sweep
│   └── calibration.py             # ECE, agreement, AUC comparison
│
├── sql/
│   └── schema.sql
│
├── notebooks/
│   └── exploration.ipynb          # Scratch only, not the deliverable
│
├── results/
│   ├── primary_analysis.csv
│   ├── silent_failures.csv
│   ├── routing_comparison.csv
│   ├── calibration.csv
│   ├── error_taxonomy.csv
│   └── figures/
│
└── .github/workflows/
    └── eval.yml
```

---

## 16. README structure

The README **is** the deliverable. Write it like a paper, not a tool doc.

```
# Yardstick

One-sentence summary.

## The question
Teams are letting LLMs write SQL against production warehouses.
When is that safe? What most teams do, and why it may be wrong.
Lead with the silent-failure framing.

## Headline findings
Three to four bullets. Numbers with confidence intervals.
Lead with the most surprising one.

## Method
Design, data, tier definitions, metric definition, result-set
comparison rules, statistical approach. Link to PREREGISTRATION.md.
State that the scorer was cross-validated against Spider's official
evaluation.

## Results
### RQ1: Does few-shot lift depend on query complexity?
### RQ2: Can difficulty be predicted and routed on?
### RQ3: Is confidence calibrated, and does disagreement predict error better?
### Silent failures: where models fail invisibly

## Deployment recommendation
Which variant for which complexity tier, when to route, when to
require human review. The practical takeaway.

## Limitations
Benchmark contamination risk. Complexity/length confound. Database
diversity. SQLite as a warehouse proxy. Sample size and minimum
detectable effect. State them plainly.

## Reproducing
Setup, run instructions, expected runtime and cost.
```

---

## 17. Non-negotiables checklist

Confirm every item before publishing.

**Design and rigor**
- [ ] Pre-registration committed **before** the full experiment ran
- [ ] Power analysis completed and reported, with minimum detectable effect stated
- [ ] McNemar's exact test used for paired binary outcomes, not a t-test
- [ ] Bootstrap confidence intervals reported, not just p-values
- [ ] Benjamini-Hochberg correction applied to primary comparisons

**Ground truth**
- [ ] Every gold query verified executable
- [ ] Zero-row gold results excluded, count logged
- [ ] 20 questions hand-reviewed for ambiguity
- [ ] Scorer cross-validated against the official Spider evaluation script

**Execution safety**
- [ ] All databases opened read-only
- [ ] 30 second timeout enforced
- [ ] Row cap enforced
- [ ] Working on copies, not originals

**Routing validity**
- [ ] Train/test split created **before** feature engineering
- [ ] **No feature derived from gold SQL.** Code-reviewed specifically
- [ ] Length-only and schema-size-only baselines reported
- [ ] Oracle upper bound reported
- [ ] Leave-one-tier-out and leave-one-database-out validation run
- [ ] Predictor validated against Spider's human difficulty labels
- [ ] Threshold sensitivity curve plotted

**Reporting honesty**
- [ ] Extraction failures scored 0, not retried, rate reported
- [ ] Silent failure rate reported per variant per tier
- [ ] Raw model outputs stored, not just scores
- [ ] Result-set comparison rules documented in README
- [ ] All three confounds stated in limitations
- [ ] Benchmark contamination risk stated explicitly
- [ ] Costs computed from actual logged tokens, not estimated
- [ ] Fixed random seeds throughout
- [ ] Pinned dependency versions
- [ ] No database files or raw dataset files committed
- [ ] Dataset license verified and attributed

---

## 18. The 90-second story

**Write this before writing code. Build toward it.**

> Teams are starting to let LLMs write SQL against production warehouses. I wanted to know when that's actually safe.
>
> I ran a 2x2 factorial experiment, two prompt strategies and two models, across 150 natural-language questions spanning three query complexity tiers. The metric was execution accuracy: does the generated query return the same result set as the human-written gold query when both are actually run against the database. That's objective, no judgment calls.
>
> Few-shot prompting closed most of the gap on simple queries and almost none on complex multi-join ones. So the naive approach of one prompt for everything fails exactly where the cost of being wrong is highest.
>
> Then I built a difficulty predictor using only features of the question and the schema, computable before generating any SQL, so routing costs nothing. It beat a length-only baseline and recovered the benchmark's human difficulty labels, and difficulty-aware routing retained most of the expensive model's accuracy at a fraction of the cost.
>
> The finding I didn't expect was about silent failures. The stronger model produced fewer errors overall, but a larger share of its errors executed cleanly and returned plausible wrong numbers, rather than throwing a syntax error. A query that fails loudly gets caught. One that returns believable numbers flows into a dashboard. So "pick the model with the highest benchmark score" turns out to be the wrong deployment heuristic.
>
> Everything was pre-registered before the full run, the significance tests are McNemar's on paired binary outcomes with bootstrap intervals and FDR correction, and I cross-validated my scorer against the official benchmark evaluation, because the naive version of this analysis produces false winners.

**If you cannot tell this story crisply, the repo existing does not help you.** The story is the point. The code is the evidence.

---

## 19. Failure modes

| Risk | Mitigation |
|---|---|
| Scope creep into a general framework | The deliverable is a study. Refuse UI work |
| Learning becomes procrastination | Build while applying and interviewing, not instead |
| No significant difference found | A null result is a finding. Report it |
| Simple tier ceilings out | Legitimate finding. Report saturation, move the primary comparison, amend pre-registration before the run with a timestamp |
| Broken gold queries poison ground truth | Validate every gold query executes in Phase 1 |
| Ambiguous questions with multiple valid answers | Hand-read 20, exclude ambiguous ones, document |
| Wrong statistical test on binary data | McNemar's, not paired t-test. Most likely error in this design |
| Gold-SQL leakage into router features | Explicit code review. Write the constraint as a comment |
| Circular routing evaluation | Split before feature engineering |
| Runaway query hangs the run | 30s timeout, row cap, subprocess kill |
| Accidental database mutation | Read-only mode, work on copies |
| Benchmark contamination | State it. Optionally cross-check on BIRD or hand-written questions |
| Rate limit destroys a long run | Write every result immediately, resumable mode |
| Comparison-logic bug found late | Executions stored separately from generations, re-score at zero API cost |
| Looker Studio connection fails at hour 70 | Decide Supabase versus Sheets export in Phase 0 |
| Cannot reproduce in six months | Pinned deps, fixed seeds, raw outputs stored |
