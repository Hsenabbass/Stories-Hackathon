# Methodology and interpretation

## Business decision

Given a known purchase and context, identify plausible lower-frequency complements and expose the financial hurdle for promoting one. The objective is decision support for an experiment. The data cannot identify an optimal discount or prove incremental profit.

There are three separate computations:

1. Estimate historical product co-purchase probabilities in masked baskets.
2. Apply explicit support, food/drink, frequency and margin rules, then rank candidates by probability times contribution.
3. Calculate the extra purchases required to cover discounting existing purchases and any specified additional costs.

The rank is an **affinity-and-margin score**. It is not predicted incremental profit. Rarity is an eligibility preference, not evidence that a product should be discounted.

## The 15% discount observation and its design consequences

The exploratory concern was discounting products that already sell frequently. Rechecking the unchanged CSV finds **504 line records at 15%**, spanning **458 transactions**, all at **Harbour**, across **nine products** in **Cold Coffee (324 lines)** and **Desserts (180 lines)**. Iced Latte accounts for 117 discounted lines and appears in 2,444 distinct baskets across the full dataset, making it the most frequently present product overall. Iced Americano and Cold Brew account for another 73 and 66 discounted lines. These are line counts, not unique customers or promotion exposures. The nine products are not all the dataset's highest-frequency products; the concern should not be generalized beyond the observed pattern.

The pattern also exists in January–April alone: 224 discounted lines, including 58 Iced Latte lines. The full-period descriptive audit is included for traceability, not fed back into model selection. Reproduce the exact counts with `python examples/audit_discounts.py`; inspect [discount_observation.json](../reports/discount_observation.json). Training/evaluation isolation does not erase the fact that the original exploration had seen the full dataset.

**Business interpretation:** if a customer would purchase at full price anyway, a 15% discount gives up contribution without producing an extra sale. But frequent sales under a promotion could also reflect a successful promotion. This purchase-only dataset has no randomized assignment, declined offers or reliable no-promotion control. The restriction to one branch and two categories makes product, branch and discount regime confounded. We cannot conclude that the campaign caused a loss, that 15% caused popularity, or that removing it would preserve sales.

That observation informed five design choices:

| Choice | Business reason and implementation |
| --- | --- |
| Target lower-frequency complements | Give quieter products exposure instead of automatically promoting the overall bestseller. `policy.py` applies the lower-half frequency rule within branch/category, using training baskets only. This is an operational targeting preference, not proof of latent demand. |
| Separate suggestion from discount | A full-price suggestion can be useful. The current UI starts at 0%; 10%–50% choices are optional scenarios, not model-endorsed prices. |
| Charge for discounting existing demand | `economics.py` includes the margin given up on purchases expected to happen anyway. Reporting discounted revenue alone would conceal this cost. |
| Do not learn discount elasticity from observed purchases | Actual discount and realized revenue/profit are excluded from classifier inputs. The classifier estimates co-purchase under the historical mixed promotion regime, not the causal effect of changing price. |
| Preserve existing stronger offers | The API and retrospective evaluator use the greater of existing and requested discounts, without stacking. The staff UI assumes no existing offer; existing Harbour promotions must be supplied through the API or reconciled in a future POS integration. |

The existing 15% promotion is an observation motivating the problem, not one of the new UI's selectable discount increments. The frozen study evaluated 0%, 5% and 10%; the later UI expanded the scenario menu to 0%, 10%, 20%, 30%, 40% and 50%. Those larger offers have calculated financial hurdles but no newly measured acceptance or uplift evidence. A 50% option can legitimately show “Not viable.”

## Data preparation

The source has 51,177 line records, 33,887 transactions, 45 products and three branches from January through June 2026. Required fields are validated for type, missingness, finiteness, numeric domains, timestamp parsing and transaction consistency. Text whitespace is normalized. Revenue and gross profit must reconcile within $0.011 per line, allowing source cent rounding. Invalid required data stops the run; identities and prices are never guessed.

There are 18,691 missing customer IDs. Customer identity is excluded from features. The 132 identical rows and 166 repeated transaction/product rows are retained because there is no line identifier to distinguish repeated purchases from export duplication. Targets, frequency and support use distinct products per transaction, so duplicates and quantity do not inflate them. Financial scenarios concern at most one offered unit. The model does not forecast quantity or total transaction revenue.

Training price/cost lookups must be constant within branch/product, as observed here. Evaluation refuses June catalog drift rather than silently using future economics. New data with changing prices requires a dated catalog. See [the data contract](data_contract.md).

### Cleaning versus feature selection

Cleaning is not synonymous with deleting rows or dropping every correlated column. We preserve the raw file, validate its meaning, derive a model-ready basket view, and retain economic fields separately for accounting. The actual audit reports **zero removed rows and zero whitespace changes**. The loader implements normalization for future inputs, but this source already passed it. Missing required identities/economics would fail the run rather than be invented. The largest revenue reconciliation error is $0.005, consistent with cent rounding; profit reconciles to floating-point precision.

| Field or redundancy | Decision | Why it is appropriate for this decision |
| --- | --- | --- |
| Product and category | Learn from the anchor product; keep category for compatibility and within-category frequency rules, not an extra classifier feature. | Each product has one category, so category is already determined by product in this dataset. This avoids a second representation of the same identity while retaining a business-useful comparison group. A category-feature ablation was not run, so no performance gain is claimed. |
| Unit price, cost, quantity, discount, revenue and gross profit | Validate all; retain training price/cost lookups for economics. Do not supply these realized basket fields to the classifier. | Revenue = quantity × price × (1 − discount); gross profit = revenue − quantity × cost. Revenue/profit are derived accounting outcomes, not independent demand signals. Including purchased-item economics or quantities could expose the completed basket. The model's target is presence, not spend or quantity. |
| Date, timestamp, hour, daypart and weekday | Parse one timestamp; use date for chronological splits, derive coarse daypart for context, test weekday as a separate ablation. Do not include raw date/time/hour alongside them. | Coarse time context reduces sparsity and avoids memorizing individual dates. Weekday is not mathematically redundant with daypart; it was tested and did not win May selection. |
| Transaction ID | Retain for grouping, audit and deterministic anchor sampling; exclude from learned inputs. | A replacement identifier is not a generalizable demand feature. It must not become a memorization shortcut. |
| Customer ID | Count missingness and exclude all customer IDs; do not impute. | 18,691 line records lack identity. A customer-specific model would require a different history and cold-start design and is unnecessary for a counter tool. Missing identity is not a reason to discard the basket. |
| Repeated rows and repeated transaction/product pairs | Retain source rows; represent unique product presence once in each basket. | Without a line key, a repeated line could be a legitimate purchase or an export duplicate. Removing it would assume facts not recorded. Unique presence prevents duplicate lines and quantity from multiplying target/support counts. Descriptive line-level audits still disclose their unit. |
| Final basket size and other purchased products | Hidden products become targets; basket size is used only in evaluation slices. | These are unknown when making the add-on suggestion. Including them would make a retrospective result look artificially strong. |

Categorical predictors are one-hot encoded using training vocabulary only. They already have a common binary scale, so no numerical standardization or PCA is needed. We did not use a correlation threshold or test-set feature importance to remove fields. Feature choices follow availability at decision time, deterministic redundancy and the business task; the explicit context/weekday ablations test whether added information helps.

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

Rank by historical compatibility probability × contribution per unit, with alphabetical tie-breaking. The default ranking uses full price and keeps the same candidate across discount scenarios. The frozen experiment uses 0%, 5% and 10%; the staff UI explicitly requests 0%–50% in ten-point steps. A separate ranking discount is an operator option. This does not optimize acceptance or profit under a discount. The interface returns an empty candidate list with a reason when rules cannot be met. Changing runtime policy settings creates a scenario outside the default evaluated policy.

Explanations show full-basket support counts, standalone counts, raw conditional frequency, raw lift and rarity. These are training observations, not model feature attribution or significance claims. Raw lift divides observed candidate frequency among anchor baskets by overall basket frequency; it is unadjusted for basket size, context or product mix. Lift can be below one even for a culinary plausible pair. Minimum support alone does not establish positive affinity. The API exposes the full evidence. The staff UI summarizes useful support and limitations behind “Why this pairing?” instead of putting raw statistics on the main workflow. Neither describes every recommendation as statistically proven.

## Evaluation

All six models share candidate eligibility and ranking margins, giving equal coverage. Primary policy hit rate is the fraction of covered examples whose chosen candidate is in the hidden basket. Abstentions are counted in coverage and excluded from conditional hit rate; hits per 1,000 total opportunities are also reported. Single-product baskets contribute misses when covered. Multi-product-only hit rate is supplementary.

Reports include unrestricted top-one match rate, candidate-level binary log loss and Brier score, selected-item Brier score and mean predicted probability, fixed-bin calibration, and branch/daypart/order-type slices. The selected model's per-transaction predictions make the hit count auditable. Day-level paired bootstrap intervals for hit differences preserve same-day correlation and pair models on the same transactions. Wilson intervals in JSON are descriptive binomial intervals; the day bootstrap is preferred for model comparison. Neither accounts for training uncertainty or repeated customers across days.

June does not demonstrate that contextual ranking outperforms popularity. A slight probability-loss advantage is useful to report but not a claim of practical superiority. Model selection remains based on May, and all comparisons are shown. No additional policy tuning is performed after inspecting June.

### Why this evaluation, and why the baseline can win

The prospective use case is a future order, so a chronological split is more realistic than randomly mixing January and June. Random row splitting would also risk putting lines from the same transaction on both sides. One deterministic masked basket per transaction preserves equal transaction weight and makes comparisons reproducible. Keeping singleton baskets prevents evaluation from assuming every customer will buy an add-on. Because purchase order is absent, this measures basket completion, not a true next-item sequence.

The simple baselines answer practical questions: would recommending a generally popular eligible item be enough; does branch/time frequency help; and are direct product-pair counts sufficient? The logistic ablations test whether sharing contextual effects improves on those counts. All models face the same availability, support, rarity and contribution rules so a model cannot win by recommending prohibited bestsellers or serving only easy cases.

May selection emphasizes log loss because downstream financial scenarios consume probabilities, not just a rank. Log loss penalizes confident wrong probabilities; Brier score and calibration provide complementary checks. This choice does **not** guarantee the highest top-one match rate or establish that probabilities are valid causal baselines. The financial hurdle is only as credible as its baseline and cost assumptions.

On June, the contextual model has 56 matches and popularity has 60 among the same 3,959 covered opportunities. The 1.41% versus 1.52% difference is small and its paired intervals include zero. Several explanations are plausible: sparse positive add-ons, restricted lower-frequency candidates, limited predictive value in the available context, and temporal variation. The study does not isolate which explanation caused the result. A stronger model cannot manufacture missing inventory or customer-intent information.

Safe next improvements are to collect exposure/rejection/stock data; validate probability calibration on development periods; compare additional features and candidate rules using forward-chaining training/validation windows; and freeze the next design before evaluating on new future data. Do not try many settings against June and report the best as a new test result. The decisive business evaluation is the randomized contribution-based pilot below, not another fraction of a percentage point in historical basket matching.

## Financial calculation

Let `b` be the baseline price after an existing discount, `s` the proposed price, `c` incremental unit cost, `q0` baseline purchase probability, `delta` the extra purchase probability, and `k` and `L` expected operating cost and substitution loss per opportunity.

```text
Incremental contribution = (q0 + delta) × (s − c) − q0 × (b − c) − k − L
                         = delta × (s − c) − q0 × (b − s) − k − L

Required additional purchases per 1,000
    = 1,000 × [q0 × (b − s) + k + L] / (s − c)
```

This threshold requires positive `s − c`. A required total probability above one is infeasible under the one-unit assumption. Equality breaks even; a gain requires exceeding the threshold. Whole-number results round up. A zero-discount, zero-cost suggestion has zero leakage, but that does not imply any extra customer will buy it.

The effective discount is the larger of the requested and existing discount. Discounts never stack or remove a better existing discount. Customer unit prices are rounded to cents using decimal round-half-up before calculating contribution. This can differ slightly from an unrounded algebraic illustration. Every requested discount, including the UI’s 0%–50% menu, is a hypothetical scenario, not a fitted price response.

Default `q0` is a historical co-purchase probability from data mixing observed discount regimes. It is a **scenario proxy**, not an identified no-offer or full-price baseline. The user can replace it per candidate. Changing a baseline discount does not re-estimate the model's probability. No claim of causality is made for that probability.

The retrospective exposure report uses actual June matches, at most one unit per transaction, and the greatest existing discount among repeated candidate lines. For each selected offer, extra discount leakage is divided by that offer's remaining unit contribution; these requirements are summed. A pooled average margin could give a different answer, so we do not use it. This assumes additional units occur in the corresponding offer groups. Existing stronger discounts are protected even in full-price scenarios. Zero operating costs and substitution in the main table are explicit simplifying assumptions. The default example's 54 sensitivity scenarios vary baseline probability by 0.5×/1×/2×, operating costs by $0/$0.01/$0.03 and substitution loss by $0/$0.02 per opportunity, across all three discount choices.

## Pilot design

Randomize eligible opportunities to no suggestion, the selected product at full price, or the same product with a prespecified discount. Freeze candidate eligibility and the model before the pilot. If staff behavior causes spillover, randomize at an appropriate block or branch/time unit and analyze with the same unit rather than pretending every transaction is independent.

Log the timestamp, known basket, context, inventory eligibility, candidate/model version, assigned arm, assignment probability, offer exposure, acceptance or rejection, actual prices, final basket and incremental costs. Record rejected offers and opportunities where nothing is purchased. Track stockouts and changes in substitution across the full basket.

Use total basket contribution per eligible opportunity as the primary outcome, with add-on purchases and operational burden as secondary measures. Set the minimum worthwhile gain, sample size and stopping rule using a prospective power calculation informed by baseline variance. Do not set a fixed duration or pretend this purchase-only CSV supplies the required exposure variance. Scale only if the prespecified uncertainty interval supports a worthwhile positive contribution after implementation costs and guardrails.

## References

The implementation follows training-only preprocessing and held-out model selection as described in [scikit-learn's common pitfalls guide](https://scikit-learn.org/1.7/common_pitfalls.html). [LogisticRegression documentation](https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.LogisticRegression.html) documents the chosen solver and regularization. The artifact stores ordinary JSON weights and counts, avoiding executable object deserialization; see [model persistence considerations](https://scikit-learn.org/1.7/model_persistence.html). The original task requirements are preserved in `docs/reference/EECE490 Stories Coffee Hackathon.docx`.
