# Results tables

Every number in the top-level [README](../README.md) traces to a CSV here. All are
regenerated from Supabase by `python scripts/export_results.py` (plus
`simulate_routing.py` and `analyze_calibration.py`, which write their own).

| File | Contents |
|---|---|
| `accuracy_by_variant_tier.csv` | accuracy, silent-failure rate, exact-match rate per variant × tier |
| `primary_analysis.csv` | **RQ1**: V2 vs V1 per tier. McNemar p, bootstrap CI, BH-adjusted p |
| `model_effect.csv` | exploratory model effect (V3 vs V1, V4 vs V2) |
| `interaction.csv` | 2×2 interaction contrast (difference-in-differences) |
| `silent_failures.csv` | silent-failure counts and rates |
| `error_taxonomy.csv` | single-bucket failure classification per variant × tier |
| `query_efficiency.csv` | median execution time of correct queries (weak proxy, see Limitations) |
| `routing_comparison.csv` | **RQ2**: six routing policies + oracle bound |
| `routing_threshold_sweep.csv` | 51-point routing accuracy cost curve |
| `calibration.csv` | **RQ3**: reliability-curve bins (mean confidence vs observed accuracy) |

## Provenance

- Restricted to `replicate = 1` (the analysed matrix) and to runs whose API call succeeded
  (`error_message IS NULL`), so free-tier rate-limit failures are treated as *pending*
  rather than as wrong answers.
- **Complete: all 600/600 matrix cells** (4 variants × 3 tiers × 50 questions) generated,
  executed, and scored. 0 extraction failures, 0 timeouts. These tables are final.
