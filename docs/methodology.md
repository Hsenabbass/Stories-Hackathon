# Methodology and interpretation

## Business decision

Given a known purchase and context, identify plausible lower-frequency complements and expose the financial hurdle for promoting one. The objective is decision support for an experiment. The data cannot identify an optimal discount or prove incremental profit.

There are three separate computations:

1. Estimate historical product co-purchase probabilities in masked baskets.
2. Apply explicit support, food/drink, frequency and margin rules, then rank candidates by probability times contribution.
3. Calculate the extra purchases required to cover discounting existing purchases and any specified additional costs.

The rank is an **affinity-and-margin score**. It is not predicted incremental profit. Rarity is an eligibility preference, not evidence that a product should be discounted.

## Data preparation

The source has 51,177 line records, 33,887 transactions, 45 products and three branches from January through June 2026. Required fields are validated for type, missingness, finiteness, numeric domains, timestamp parsing and transaction consistency. Text whitespace is normalized. Revenue and gross profit must reconcile within $0.011 per line, allowing source cent rounding. Invalid required data stops the run; identities and prices are never guessed.

There are 18,691 missing customer IDs. Customer identity is excluded from features. The 132 identical rows and 166 repeated transaction/product rows are retained because there is no line identifier to distinguish repeated purchases from export duplication. Targets, frequency and support use distinct products per transaction, so duplicates and quantity do not inflate them. Financial scenarios concern at most one offered unit. The model does not forecast quantity or total transaction revenue.

Training price/cost lookups must be constant within branch/product, as observed here. Evaluation refuses June catalog drift rather than silently using future economics. New data with changing prices requires a dated catalog. See [the data contract](data_contract.md).

## Example construction and leakage controls

For each transaction, sort its unique products, use a fixed SHA-256 hash of seed plus transaction ID to pick one anchor, and treat remaining products as binary targets. This yields one row per transaction, keeps large baskets from receiving greater training weight, and is invariant to file order and duplicated lines. The anchor is not an observed first purchase. Single-product baskets have all-negative add-on targets and remain in every score denominator.

Training uses 20,542 January–April baskets, validation uses 6,439 May baskets, and evaluation uses 6,906 June baskets. Transactions cannot cross dates/splits. The artifact remains fitted to January–April after May selection, so June scores apply to the exact serving artifact.

Product vocabulary, one-hot vocabulary, popularity ranks, pairing support, catalogs, smoothing priors and coefficients use training only. May selects hyperparameters and model family. June computes final metrics only. Customer IDs, quantities, actual discounts, revenue, profit, target products and final basket size never become model features. Weekday is derived from the date but tested separately. The original exploratory discussion examined the full dataset; that limitation is disclosed in every main report.

## Models and parameters

| Family | Estimate |
| --- | --- |
| Global popularity | Candidate target rate among examples where it is not the anchor, with a Beta(0.5, 0.5) prior |
| Context popularity | Candidate rates by branch and daypart, smoothed toward global rates |
| Pair | Candidate rates by anchor product, smoothed toward global rates |
| Anchor logistic | One regularized binary logistic model per candidate, anchor feature only |
| Context logistic | Anchor, branch, daypart and order type |
| Weekday logistic | Context plus weekday |

For each candidate, rows where it is the anchor are excluded from fitting. Otherwise the model would be taught structural negative targets for an item that is already known to be present. Prediction sets anchor probability to zero. Unknown one-hot levels contribute zero for that feature; count models back off to their global prior. The serving tool rejects unknown products and branches. Overnight is exposed as an unsupported context with a warning.

Each logistic model uses one-hot encoding, an unpenalized intercept, L2 regularization and LBFGS. The inputs are binary indicators, so numeric scaling is unnecessary. C is the inverse regularization strength, tuned over 0.01, 0.1, 1 and 10. Smoothing strengths are 10, 50 and 200 pseudo-observations. There is no class balancing, oversampling or negative subsampling because those would alter the prevalence underlying the financial probabilities. Convergence warnings fail training. A constant-target fallback uses the smoothed candidate prior.

These small models share context effects across anchors, which helps sparse combinations. We deliberately do not fit separate models for every branch/hour/weekday/product cell, add neural networks, or claim learned discount elasticity. Higher complexity is not justified by this dataset or the task. Anchor-only logistic and pair baselines test whether additional context helps. Weekday is retained only as an alternative because validation favored the context model without it.

All 19 hyperparameter trials are recorded in `reports/validation.json`. The selection criterion is mean binary log loss over the **same eligible candidate matrix** for every model. This prioritizes usable probability estimates for financial scenarios rather than selecting by a small, noisy difference in top-one accuracy. No probability recalibration is fitted using June. Log loss and Brier comparisons on sparse labels must be read alongside positive frequency and calibration; a low absolute loss by itself does not imply strong recommendations.

## Candidate policy and explanations

Candidates must satisfy all of the following training-only conditions:

- Opposite food/drink group to the anchor. This is a deliberately narrow culinary assumption, not an inference about dietary safety or personal preferences.
- At least 20 distinct co-purchase baskets with the anchor, across branches.
- At least 100 distinct training baskets containing the candidate.
- At or below the 50th percentile of training basket counts within the candidate's own branch/category. Ranks use average ties divided by category size. All-tied categories can have no lower-half member.
- Positive contribution at the ranking discount, and presence in the branch's training catalog.

Inventory and already-present basket items can further restrict the runtime candidate set. The original evaluations assume catalog availability because actual stock is not recorded. Excluding additional known basket items does not make the probability model conditional on those items; it still uses the anchor and context only.

Rank by historical compatibility probability × contribution per unit, with alphabetical tie-breaking. The default ranking uses full price and the same candidate across the 0%, 5% and 10% scenarios. A separate ranking discount is an operator option. This does not optimize acceptance or profit under a discount. The interface returns an empty candidate list with a reason when rules cannot be met. Changing runtime policy settings creates a scenario outside the default evaluated policy.

Explanations show full-basket support counts, standalone counts, raw conditional frequency, raw lift and rarity. These are training observations, not model feature attribution or significance claims. Raw lift divides observed candidate frequency among anchor baskets by overall basket frequency; it is unadjusted for basket size, context or product mix. Lift can be below one even for a culinary plausible pair. Minimum support alone does not establish positive affinity. The interface exposes that evidence rather than describing every recommendation as statistically proven.

## Evaluation

All six models share candidate eligibility and ranking margins, giving equal coverage. Primary policy hit rate is the fraction of covered examples whose chosen candidate is in the hidden basket. Abstentions are counted in coverage and excluded from conditional hit rate; hits per 1,000 total opportunities are also reported. Single-product baskets contribute misses when covered. Multi-product-only hit rate is supplementary.

Reports include unrestricted top-one match rate, candidate-level binary log loss and Brier score, selected-item Brier score and mean predicted probability, fixed-bin calibration, and branch/daypart/order-type slices. The selected model's per-transaction predictions make the hit count auditable. Day-level paired bootstrap intervals for hit differences preserve same-day correlation and pair models on the same transactions. Wilson intervals in JSON are descriptive binomial intervals; the day bootstrap is preferred for model comparison. Neither accounts for training uncertainty or repeated customers across days.

June does not demonstrate that contextual ranking outperforms popularity. A slight probability-loss advantage is useful to report but not a claim of practical superiority. Model selection remains based on May, and all comparisons are shown. No additional policy tuning is performed after inspecting June.

## Financial calculation

Let `b` be the baseline price after an existing discount, `s` the proposed price, `c` incremental unit cost, `q0` baseline purchase probability, `delta` the extra purchase probability, and `k` and `L` expected operating cost and substitution loss per opportunity.

```text
Incremental contribution = (q0 + delta) × (s − c) − q0 × (b − c) − k − L
                         = delta × (s − c) − q0 × (b − s) − k − L

Required additional purchases per 1,000
    = 1,000 × [q0 × (b − s) + k + L] / (s − c)
```

This threshold requires positive `s − c`. A required total probability above one is infeasible under the one-unit assumption. Equality breaks even; a gain requires exceeding the threshold. Whole-number results round up. A zero-discount, zero-cost suggestion has zero leakage, but that does not imply any extra customer will buy it.

The effective discount is the larger of the requested and existing discount. Discounts never stack or remove a better existing discount. Customer unit prices are rounded to cents using decimal round-half-up before calculating contribution. This can differ slightly from an unrounded algebraic illustration. A 5% or 10% request is a hypothetical menu, not a fitted price response.

Default `q0` is a historical co-purchase probability from data mixing observed discount regimes. It is a **scenario proxy**, not an identified no-offer or full-price baseline. The user can replace it per candidate. Changing a baseline discount does not re-estimate the model's probability. No claim of causality is made for that probability.

The retrospective exposure report uses actual June matches, at most one unit per transaction, and the greatest existing discount among repeated candidate lines. For each selected offer, extra discount leakage is divided by that offer's remaining unit contribution; these requirements are summed. A pooled average margin could give a different answer, so we do not use it. This assumes additional units occur in the corresponding offer groups. Existing stronger discounts are protected even in full-price scenarios. Zero operating costs and substitution in the main table are explicit simplifying assumptions. The default example's 54 sensitivity scenarios vary baseline probability by 0.5×/1×/2×, operating costs by $0/$0.01/$0.03 and substitution loss by $0/$0.02 per opportunity, across all three discount choices.

## Pilot design

Randomize eligible opportunities to no suggestion, the selected product at full price, or the same product with a prespecified discount. Freeze candidate eligibility and the model before the pilot. If staff behavior causes spillover, randomize at an appropriate block or branch/time unit and analyze with the same unit rather than pretending every transaction is independent.

Log the timestamp, known basket, context, inventory eligibility, candidate/model version, assigned arm, assignment probability, offer exposure, acceptance or rejection, actual prices, final basket and incremental costs. Record rejected offers and opportunities where nothing is purchased. Track stockouts and changes in substitution across the full basket.

Use total basket contribution per eligible opportunity as the primary outcome, with add-on purchases and operational burden as secondary measures. Set the minimum worthwhile gain, sample size and stopping rule using a prospective power calculation informed by baseline variance. Do not set a fixed duration or pretend this purchase-only CSV supplies the required exposure variance. Scale only if the prespecified uncertainty interval supports a worthwhile positive contribution after implementation costs and guardrails.

## References

The implementation follows training-only preprocessing and held-out model selection as described in [scikit-learn's common pitfalls guide](https://scikit-learn.org/1.7/common_pitfalls.html). [LogisticRegression documentation](https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.LogisticRegression.html) documents the chosen solver and regularization. The artifact stores ordinary JSON weights and counts, avoiding executable object deserialization; see [model persistence considerations](https://scikit-learn.org/1.7/model_persistence.html). The original task requirements are preserved in `docs/reference/EECE490 Stories Coffee Hackathon.docx`.
