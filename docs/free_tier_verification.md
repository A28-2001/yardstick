# Phase 0. Free-tier & data-source verification

**Verified: 2026-07-21** (terms change; re-check before a long run). Each row cites its source.

> **DESIGN DECISION (2026-07-21): fully free, no paid provider.** The "expensive model"
> factor (V3/V4) was changed from Claude to a **larger Groq model**. The 2×2 is now
> **prompt strategy × model size**: V1/V2 = Llama-3.1-8B (cheap), V3/V4 = Llama-3.3-70B
> (strong). Both run on Groq's free tier. Cost/routing analysis (RQ2) uses **published
> per-token list prices** for 8B vs 70B as the cost proxy (§13.3), so the savings story
> stays real even though our spend is $0. Anthropic is dropped from the required path.

## Free-tier terms

| Service | What we get (free) | Binding constraint for Yardstick | Source |
|---|---|---|---|
| **Groq** | Per-model limits. `llama-3.3-70b-versatile` ≈ **30 RPM, 1,000 req/day, 12K tokens/min, 100K tokens/day** (as of 2026-06-04). No card required. | **100K tokens/day is the real ceiling.** Prompts carry the schema DDL, so input tokens dominate (~1 to 3K/call). The full Groq load (V1+V2 = ~300 calls) can exceed one day's token budget → **spread across days; the cache + resumable mode (§8.1) absorb this cleanly.** | [pricepertoken](https://pricepertoken.com/endpoints/groq/free), [tokenmix](https://tokenmix.ai/blog/groq-free-tier-limits-2026) |
| **Anthropic (Claude)** | ~~$5 signup credit~~ | **DROPPED from the design**, kept the project 100% free. Was the only paid dependency. Can be re-added later as an optional cross-provider check if credit is ever added. |, |
| **Supabase** | **500 MB** DB, 2 active projects, **paused after 7 days inactivity** (data retained, ~30s to resume). | 600 runs + 150 questions is kilobytes, capacity is a non-issue. **Watch the 7-day inactivity pause**: if we go quiet mid-study the project sleeps (just resume it). | [uibakery](https://uibakery.io/blog/supabase-pricing), [itpathsolutions](https://www.itpathsolutions.com/supabase-free-tier-limits) |
| **GitHub Actions** | **Unlimited on public repos**; 2,000 Linux min/month on private (Free plan). | Phase 11 automation is light. If the repo is public, effectively free. | [cicdcalculator](https://cicdcalculator.com/github-actions-free-tier) |

### Capacity sanity check (Groq-only design)
- Full experiment = 150 questions × 4 variants = **600 generation calls**, now ALL on Groq:
  300 on the 8B model (V1,V2) + 300 on the 70B model (V3,V4). Plus ~60 pilot calls.
- **Binding constraint: the 70B model's ~100K tokens/day.** With schema DDL in each prompt
  (~1 to 2.5K input tokens/call), the ~300 70B calls likely span **several days**. The 8B model
  has higher free limits and is less constrained.
- **This is a non-issue operationally** because of the design: write-after-every-call +
  resumable run mode + generation cache mean hitting a daily token cap just pauses the run;
  resume the next day at **zero re-cost**. The pilot (10 questions) fits easily in one day.
- Exact per-model Groq limits are account-specific, **confirm in your Groq console →
  Settings → Limits** before the full run.

## Data source. IMPORTANT

**The Hugging Face `xlangai/spider` dataset ships ONLY question-SQL text pairs (Parquet), NOT the SQLite database files.**
The study's execution-accuracy metric (§9.2) requires *executable* databases, so:

- **Question-SQL pairs + difficulty labels:** Hugging Face `xlangai/spider` (train 7,000 / validation 1,030), CC-BY-SA-4.0, no auth/gating.
- **The actual SQLite databases (`database/<db_id>/<db_id>.sqlite`):** come from the **official Yale LILY Spider bundle** (linked from https://yale-lily.github.io/spider, a Google-Drive `spider_data.zip`). This zip also contains `tables.json`, `train_gold.sql`, `dev_gold.sql`.
- `scripts/download_data.py` (Phase 1) must therefore fetch **both**: the pairs/labels AND the database bundle. Neither is committed to the repo (`.gitignore` excludes `data/` and `databases/`).
- Spider's held-out **test** split is not public; we work from **train + dev**, which is fine. 150 sampled questions with capped per-db counts.

**License:** Spider is **CC BY-SA 4.0**, attribute Yale LILY, note the license in the README, and any derived data shared inherits share-alike.

## Sources
- Groq: https://pricepertoken.com/endpoints/groq/free · https://tokenmix.ai/blog/groq-free-tier-limits-2026
- Anthropic: https://tokenmix.ai/blog/free-claude-api-credits-2026-guide · https://tygartmedia.com/anthropic-console-developer-guide-2026/
- Supabase: https://uibakery.io/blog/supabase-pricing · https://www.itpathsolutions.com/supabase-free-tier-limits
- GitHub Actions: https://cicdcalculator.com/github-actions-free-tier
- Spider: https://yale-lily.github.io/spider · https://huggingface.co/datasets/xlangai/spider
