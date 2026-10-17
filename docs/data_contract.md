# Data contract and provenance

The supplied transaction CSV is preserved byte-for-byte in `data/raw/stories_transactions.csv`. The original brief is preserved in `docs/reference/EECE490 Stories Coffee Hackathon.docx`. The generated audit and artifact both contain the CSV SHA-256. Evaluation requires the same source hash used for fitting.

The brief calls the records real transaction data with replacement transaction IDs. IDs beginning with `SYN-` are treated as opaque replacement identifiers; their prefix does not establish a different provenance. No external enrichment or invented customer records are used.

## Required source fields

| Column | Contract and use |
| --- | --- |
| Transaction ID | Non-empty opaque string; groups a completed basket |
| Date / Time | Parseable `YYYY-MM-DD` / `HH:MM:SS`; consistent within transaction |
| Branch | Non-empty string, consistent within transaction; model feature and catalog lookup |
| Customer ID | May be absent; ignored by the model |
| Order Type | `Dine-in` or `Takeaway`; consistent within transaction |
| Product / Category | Non-empty; product must map to one category |
| Quantity | Finite positive integer; validated but not a model feature |
| Unit Price (USD) | Finite and positive; constant by branch/product in training |
| Discount Rate | Finite fraction in `[0, 1)`; validation and historical exposure only |
| Unit Cost (USD) | Finite and nonnegative; constant by branch/product in training |
| Line Revenue (USD) | Quantity × unit price × (1 − discount), within rounding tolerance |
| Line Gross Profit (USD) | Revenue − quantity × unit cost, within rounding tolerance |

Extra columns are ignored. Required missing values or inconsistent metadata stop training. No outlier is removed merely because it is unusual. Missing customer IDs are counted, not imputed. Exact repeated rows are reported and retained because the source has no unique line key.

## Derived quantities

Frequency and support count baskets with the product present, once per product/basket. “Standalone” means a basket containing only one distinct product, even when quantity exceeds one. Rarity is basket frequency within branch/category; it is not inventory-adjusted demand, sales against target, or revenue rank.

One hashed anchor is sampled per transaction. Features contain only the anchor, branch, coarse daypart, order type and optionally weekday. Targets are all remaining unique products. Final basket size is retained only for evaluation slices. Unit prices and costs do not enter the classifier. There is no customer-history model.

## Redundant fields and model boundaries

The raw CSV is never reduced to just classifier columns. Category is determined by product; revenue and gross profit are computed from the other accounting fields; raw time is summarized into daypart. These redundant representations are retained for validation, policy or economics but excluded from classifier inputs. Customer identity and realized basket outcomes are excluded for different reasons—missingness, scope and leakage—not because all excluded fields are mathematically redundant. See the [field-by-field decisions](methodology.md#cleaning-versus-feature-selection).

[The actual cleaning audit](../reports/data_audit.json) records zero removed rows, zero trimmed cells, 132 identical rows retained and 166 repeated transaction/product rows. These duplicate counts overlap and must not be added together as separate groups.

## New data

Configured time windows must be non-overlapping and strictly ordered, and every source date must fall inside the study window. All three periods must be non-empty. Out-of-vocabulary validation/test products are rejected rather than silently deleted. New categories require an explicit food/drink group. New products need a cold-start eligibility design and fresh evaluation. Variable prices/costs need dated lookups; the present study deliberately requires fixed training values and checks June consistency.

The input records do not contain inventory, footfall, declined offers, offer impressions, randomized assignment, order of purchase or reliable causal baseline probabilities. These absences limit what the outputs mean and define the next data collection task.
