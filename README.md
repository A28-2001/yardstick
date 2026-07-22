# Yardstick

*Does prompt engineering for text-to-SQL depend on query complexity — and can that
difficulty be predicted, before generating any SQL, and used to route cost-effectively?*

> **Status:** 🚧 In progress. Phase 0 (setup) underway. This README is the deliverable
> and is written as a research writeup; sections below fill in as phases complete.
> The full build spec lives in [`yardstick_project_spec.md`](yardstick_project_spec.md).

---

## The question

Teams are letting LLMs write SQL against production warehouses. Most validate on a
benchmark, pick the winning prompt, and deploy it uniformly. **When is that safe, and
where does it stop being safe?**

A SQL query that throws a syntax error is a *visible* failure. A query that executes
cleanly and returns plausible but wrong numbers is an *invisible* one — it flows into a
dashboard or a decision. This study measures how often that happens, and whether the
"pick the highest benchmark score" heuristic is the wrong deployment call.

## Headline findings

_TBD — filled in after Phase 7–9. Three to four bullets with confidence intervals,
most surprising first._

## Method

- **Design:** 2×2 factorial (prompt strategy × model size) across three complexity tiers.
  V1 zero-shot/Llama-8B, V2 few-shot/Llama-8B, V3 zero-shot/Llama-70B, V4 few-shot/Llama-70B
  (both models on Groq's free tier; cost analysis uses published per-token list prices).
- **Data:** Spider (ships executable SQLite databases). 150 questions, 50 per tier,
  tiers defined by Spider's human difficulty labels (easy→Simple, medium→Moderate,
  hard+extra→Complex). Capped at 3 questions per database.
- **Primary metric:** execution accuracy — does the generated query return the same
  result set as the gold query when both are run against the database (set-based
  comparison, order-insensitive unless the gold query has `ORDER BY`). Objective, no
  LLM judge.
- **Result-set comparison rules:** _documented in [§9.2 of the spec]; summarized here
  after Phase 3._
- **Statistics:** McNemar's exact test on paired binary outcomes, bootstrap CIs,
  Benjamini-Hochberg FDR correction on the three primary comparisons. Pre-registered.
- **Scorer** cross-validated against the official Spider evaluation script (Phase 3).

See [`PREREGISTRATION.md`](PREREGISTRATION.md) _(committed at Phase 4, before the full run)_.

## Results

### RQ1 — Does few-shot lift depend on query complexity?
_TBD (Phase 7)_

### RQ2 — Can difficulty be predicted and routed on?
_TBD (Phase 8)_

### RQ3 — Is confidence calibrated, and does disagreement predict error better?
_TBD (Phase 9)_

### Silent failures — where models fail invisibly
_TBD (Phase 7)_

## Deployment recommendation
_TBD (Phase 9–10). Which variant for which tier; when to route; when to require human review._

## Limitations
_TBD (Phase 10). Benchmark contamination risk; complexity/length confound; database
diversity; SQLite as a warehouse proxy; sample size & minimum detectable effect._

## Reproducing

```bash
# 1. Install (pinned)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env        # fill in GROQ / ANTHROPIC keys + Supabase DATABASE_URL

# 3. Apply the results schema to Supabase
psql "$DATABASE_URL" -f sql/schema.sql

# 4. Verify setup (Phase 0 exit criteria)
python scripts/verify_setup.py
```

Expected runtime and cost: _TBD._

## Data & attribution

- **Spider** (questions, gold SQL, SQLite databases) — Yale LILY lab, **CC BY-SA 4.0**,
  https://yale-lily.github.io/spider. Downloaded by `scripts/download_data.py`; no
  dataset files are committed (gitignored).
- **Official Spider evaluation scripts** — vendored under `third_party/spider_eval/`
  from https://github.com/taoyds/spider (see that folder's README for how they're used).
