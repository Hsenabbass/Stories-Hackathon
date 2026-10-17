# Evaluation results

May validation selected **context_logistic** before June evaluation. June contains 6,906 masked baskets; the fixed promotion policy covers 3,959 (57.3%).

Each opportunity reveals one reproducibly sampled product from a completed basket. Single-product baskets remain in the denominator. A hit means the suggested product was also present, not that a customer accepted an offer.

## Model comparison

All policies use identical training-only candidate rules and full-price contribution ranking. Lower log loss/Brier is better. Hit rate is among covered opportunities.

| Model | May selected | June policy hit rate | Eligible log loss | Eligible Brier | Mean predicted probability |
| --- | --- | ---: | ---: | ---: | ---: |
| anchor_logistic |  | 1.16% | 0.07630 | 0.01440 | 1.49% |
| context_logistic | Yes | 1.41% | 0.07616 | 0.01439 | 1.56% |
| context_popularity |  | 1.52% | 0.07629 | 0.01440 | 1.19% |
| global_popularity |  | 1.52% | 0.07627 | 0.01440 | 1.13% |
| pair |  | 1.16% | 0.07679 | 0.01441 | 1.81% |
| weekday_logistic |  | 1.41% | 0.07631 | 0.01440 | 1.58% |

## Paired uncertainty

Differences below are selected-model minus comparator hit rates, in percentage points. Intervals resample whole June days together across both policies (2,000 draws). They do not include model-fitting uncertainty, repeated customers across days, or future drift.

| Comparator | Difference | 95% day-bootstrap interval |
| --- | ---: | ---: |
| anchor_logistic | 0.25 pp | [-0.03, 0.54] pp |
| context_popularity | -0.10 pp | [-0.36, 0.15] pp |
| global_popularity | -0.10 pp | [-0.40, 0.22] pp |
| pair | 0.25 pp | [-0.05, 0.54] pp |
| weekday_logistic | 0.00 pp | [-0.19, 0.18] pp |

## Historical discount exposure

One unit of the selected add-on per opportunity. Existing stronger discounts are preserved, never stacked. Requirements sum each offer's exposure divided by its own remaining margin; they assume extra purchases arise in those same offer groups. They are descriptive hurdles, not forecast sales or profit.

| Requested discount | Extra discount on historical purchases | Required extra units per 1,000 covered opportunities |
| ---: | ---: | ---: |
| 0% | $0.00 | 0.00 |
| 5% | $14.06 | 1.27 |
| 10% | $28.16 | 2.83 |

## Interpretation and limits

Model choice is based on May eligible-candidate log loss because the financial tool consumes probabilities. The June ranking does not change that choice. Compare the paired intervals before claiming any ranking improvement. Calibration bins and branch/daypart slices are available in the JSON reports.

Under-selling means the lower half of observed training basket counts within the same branch and category. Missing inventory, footfall, offer impressions and counterfactual purchases prevent a claim of unmet demand or causal sales uplift. Source costs are assumed to approximate incremental costs. Operating costs and substitution are zero in the table and adjustable in the tool.

Chronological backtest. This dataset had been explored in earlier discussion; June is not wholly untouched external confirmation. No causal uplift measured.

The executable protocol, assumptions, and proposed randomized test are in [methodology](../docs/methodology.md). Machine-readable results accompany this report.
