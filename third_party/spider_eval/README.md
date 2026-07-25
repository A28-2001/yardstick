# Vendored: official Spider evaluation scripts

`evaluation.py` and `process_sql.py` are copied verbatim from the official Spider
repository:

- Source: https://github.com/taoyds/spider (Yale LILY lab)
- Fetched: 2026-07-22

They are used for two purposes in Yardstick:

1. **Tier labeling**, the query-hardness algorithm (`eval_hardness` and its helpers)
   is the basis for our complexity tiers. We re-implement just that slice in
   `yardstick/hardness.py` (verbatim) to avoid the `nltk` dependency that
   `process_sql.py` pulls in.
2. **Scorer cross-check (Phase 3)**, we validate our own execution-accuracy scorer
   against the official script on a subset of questions (spec §9.3).

The **Spider dataset** itself (questions, gold SQL, databases) is distributed by
Yale LILY under **CC BY-SA 4.0**: https://yale-lily.github.io/spider
No dataset files are committed to this repo (they are downloaded by
`scripts/download_data.py` and gitignored).
