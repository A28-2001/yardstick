# Claims and their sources

Every headline number on the [site](https://a28-2001.github.io/yardstick/), in the
[report](https://a28-2001.github.io/yardstick/report.html) and in the [README](README.md),
with the file or script that produces it. If a number is not here or in `results/`, it
should not be on the site.

**Audit, November 2026.** Every factual sentence across the site, report, README and figures
was checked against the data. 64 failed and were rewritten. Most were overstatements: a
trend the data does not support, words like "plausible" or "believable" for things that were
never measured, a misread p-value, and a claim that people score near chance on the quiz,
which nothing measured. The study's results and its pre-registration did not change; only
how they were described.

Sources:
- `results/*.csv`: the published results, written by the analysis scripts.
- `scripts/analyze_supplementary.py`: numbers the prose cites that no other script computed,
  plus the checks behind the audit.
- `docs/data/runs.json`: one record per run, the same data the site loads.

## Mistakes and silent failures

| Claim | Value | Source |
|---|---|---|
| Wrong answers out of 600 | 104 | `runs.json`, `results/variant_summary.csv` |
| Wrong answers that ran without any error (silent) | 93 of 104 (89%, 95% CI 82 to 95%) | `analyze_supplementary.py` §1 |
| Most accurate setup (V3, Llama 3.3 70B, no examples) | 89% accurate; 17 of 17 mistakes silent | `results/variant_summary.csv` |
| Silent share by setup | V1 89%, V2 81%, V4 95%, V3 100% | `results/variant_summary.csv` |
| Silent share by difficulty | simple 95%, moderate 97%, complex 82% | `runs.json` |
| Larger vs smaller model, silent share | 36 of 37 vs 57 of 67, Fisher exact p = 0.092 (not significant) | `analyze_supplementary.py` §1 |
| Loud failures | 11, all invented tables or columns | `analyze_supplementary.py` §1 |
| Mistakes where the AI said it was at least 90% sure | 93 of 104 | `analyze_supplementary.py` §1 |
| Mistakes with no warning: ran without an error and stated confidence at least 90% | 84 of 104 (81%, "4 in 5") | `runs.json`, `docs/js/facts.js` |
| All answers with stated confidence at least 90% | 581 of 600 | `runs.json`, `docs/js/facts.js` |
| No-warning mistakes that are only a wrong column (right information, extra or missing column) | 11 of 84; without them, 73 of 93 (78%) | `runs.json` (`err` = `wrong_projection`), `docs/js/facts.js` |
| Example on the first screen (csu_1, `q795bbdf3dc7d`, "Which year has the most degrees conferred?") | V2 returned 2002, ran without error, confidence 0.9; V1, V3 and V4 returned 2004 (V1 scored wrong for an extra column); gold 2004 | `runs.json`, re-executed on `databases/csu_1/csu_1.sqlite` |

## The cross-check

The rule: run every question through all four setups and flag it when they do not all
return the same rows.

| Claim | Value | Source |
|---|---|---|
| Questions flagged | 42 of 150 (168 of 600 outputs, 28%) | `analyze_supplementary.py` §2 |
| Mistakes caught | 87 of 104 (84%) | `analyze_supplementary.py` §2 |
| Correct outputs flagged (false alarms) | 81 of 496 (16%) | `analyze_supplementary.py` §2 |
| Mistakes in unflagged questions | 17 of 104 (9 of them failed with an error; 8 silent) | `analyze_supplementary.py` §2, `docs/js/facts.js` |
| No-warning mistakes caught | 77 of 84 (92%, "about 9 in 10") | `runs.json` (`flagged`), `docs/js/facts.js` |
| Flagged outputs that were actually correct | 81 of 168 (48%, "about half") | `runs.json` (`flagged`), `docs/js/facts.js` |
| Judged correctly on a balanced mix | 84% of all 600 | `analyze_supplementary.py` §2 |
| Predicting correctness, AUC | agreement 0.861, stated confidence 0.647; gap 0.215, 95% CI [0.12, 0.30] | `analyze_supplementary.py` §3, `scripts/analyze_calibration.py` |
| Cost of four setups per question | about $0.0011 at list prices | `docs/data/yardstick_runs.csv` |

A version with only two setups was not measured.

## Prompting and model

| Claim | Value | Source |
|---|---|---|
| Few-shot lift (pre-registered) | simple -2, moderate 0, complex +8 pts (p = 0.42); none significant | `results/primary_analysis.csv` |
| Larger, newer model on complex questions (exploratory) | +28 pts, 60% to 88%, CI [+14, +42], p = 0.0013; survives Benjamini Hochberg | `results/model_effect.csv`, `analyze_supplementary.py` §8 |
| Same, with examples | +16 pts, p = 0.039; does not survive correction | `results/model_effect.csv`, `analyze_supplementary.py` §8 |
| Moderate questions | every setup 82 to 84% | `results/accuracy_by_variant_tier.csv` |

"Model" means Llama 3.1 8B against Llama 3.3 70B, so the comparison mixes size and version.

## Confidence

| Claim | Value | Source |
|---|---|---|
| Weakest setup | stated 98.6% confidence, 76.7% correct | `results/variant_summary.csv` |
| Confidence on wrong answers | 87 to 96% across the four setups | `results/variant_summary.csv` |
| Confidence on right vs wrong answers | V1 0.99/0.96, V2 0.94/0.93, V3 0.99/0.95, V4 0.93/0.87 | `analyze_supplementary.py` §4 |
| Overconfidence gap | V1 22, V2 15, V3 10, V4 6 pts | `results/variant_summary.csv` |

## Routing and cost

| Claim | Value | Source |
|---|---|---|
| Predicting which questions the cheap model fails, AUC | length only 0.724, six features 0.665, schema size 0.507 | `scripts/train_router.py` |
| Difficulty routing accuracy | 78.3% at 28% of the expensive model's cost | `results/routing_comparison.csv` |
| Random routing at the same budget | one seeded draw 78.3%; 100,000 draws average 75.5%; 21.6% of draws tie or beat the router | `results/routing_comparison.csv`, `analyze_supplementary.py` §5 |
| Oracle routing | 90.0% at 37% of the expensive model's cost | `results/routing_comparison.csv` |
| What tracks cost and difficulty (Pearson r) | schema tables vs cost 0.93, vs difficulty 0.03; question length vs cost 0.25, vs difficulty 0.30 | `analyze_supplementary.py` §6 |
| Input share | 95% of tokens, 93% of spend | `analyze_supplementary.py` §7 |
| List-price cost of the 600 runs | $0.17 (actual spend $0, free tier) | `analyze_supplementary.py` §7 |

## Method

| Claim | Value | Source |
|---|---|---|
| Sample | 150 questions, 50 per difficulty level, 93 databases | `data/questions.json`, `results/README.md` |
| Scorer vs the official Spider evaluator | agrees on 18 of the 19 queries the official tool could score; it could not parse 11 of 30 | `docs/scorer_crosscheck.md` |
| Replicates | verdicts identical across 3 replicates in the pilot; SQL text varied in 3 of 40 cells | `PREREGISTRATION.md` |
| 10,000-row cap | hit by 2 queries | `analyze_supplementary.py` §1 |

## Reproducing

```bash
python scripts/rebuild_db.py
python scripts/analyze_supplementary.py
```

`rebuild_db.py` restores the results database from the committed files. The original
hosted database is no longer available; see that script for what it can and cannot
recover.
