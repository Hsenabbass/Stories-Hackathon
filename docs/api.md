# Tool and API contract

All dollar amounts are USD. Discounts and probabilities are fractions: `0.05` means 5%. One opportunity is a basket with one known anchor. Alternatives are mutually separate proposals; the tool does not estimate acceptance of a multi-item bundle.

## Run locally

```bash
python -m stories_promo serve --port 8000
```

The model loads once at server startup. Restart to load a new artifact. `--artifact` selects another JSON bundle. The default host is `127.0.0.1`; nothing is published. Interactive validation and requests are available at `http://127.0.0.1:8000/docs`, with an OpenAPI schema at `/openapi.json`.

The promotion studio UI is served at `/` by the same application. Its assets live under `/assets`, and its requests use the existing same-origin `/options` and `/recommend` endpoints.

| Route | Use |
| --- | --- |
| `GET /health` | Check readiness and selected model |
| `GET /options` | Products by branch, dayparts, weekdays, models, defaults and provenance |
| `POST /recommend` | Rank candidates and calculate each discount scenario |

## Request

The five required context fields are:

```json
{
  "anchor": "Iced Matcha",
  "branch": "Garden",
  "daypart": "afternoon",
  "weekday": "Tuesday",
  "order_type": "Dine-in"
}
```

| Optional field | Default | Meaning |
| --- | --- | --- |
| `model` | May-selected family | One of the six names from `/options`; alternatives are comparison tools |
| `top_k` | `3` | Number of alternatives, from 1 to 10 |
| `discounts` | Artifact policy: `[0, 0.05, 0.1]` | Scenarios for each suggested product; fractions in `[0, 1)` |
| `ranking_discount` | Artifact policy: `0` | Discount used in affinity × contribution ranking; separate from compared offers |
| `baseline_discount` | `0` | Existing candidate discount; stronger discounts are retained |
| `max_popularity_percentile` | Artifact policy: `0.5` | Within-branch/category frequency cutoff in `(0, 1]`; larger values allow more popular items |
| `available_products` | `null` | Explicit inventory allow-list; `[]` means no stock and produces abstention |
| `already_in_basket` | `[]` | Candidates to exclude; does not add conditioning features |
| `baseline_probability_overrides` | `{}` | Per-candidate baseline probability for economics; does not change model ranking |
| `operating_cost_per_opportunity` | `0` | Added expected dollar cost per eligible opportunity |
| `substitution_loss_per_opportunity` | `0` | Expected lost contribution per opportunity from substitution or related effects |

The staff UI explicitly sends `discounts: [0, 0.1, 0.2, 0.3, 0.4, 0.5]` and selects 0% initially. The original artifact defaults remain frozen for reproduction of the study; UI scenarios do not modify them.

An omitted or null policy-default field uses the saved artifact's configuration. Invalid enum values, non-finite numbers, unknown fields, unsupported models, or products absent from the chosen branch's training catalog produce HTTP 422. CLI errors have exit code 2. API errors do not return a fabricated recommendation.

Dayparts use local transaction clock time: morning 07:00–10:59, midday 11:00–15:59, afternoon 16:00–19:59, evening 20:00–23:59 and overnight 00:00–06:59. Overnight has no observations here, so it is flagged. No timezone is inferred or converted for the source.

## Response

`schema_version` is `1`. `status` is `recommended` or `abstained`. A successful abstention is HTTP 200 with an empty `recommendations` array and `abstention_reason`.

Every candidate contains:

- `product`, `category`, historical co-purchase probability and affinity-margin score.
- `evidence`: training counts, standalone support, raw conditional frequency/lift and within-branch/category popularity.
- `economics_baseline_source`: `historical_probability_proxy` or `user_scenario`.
- `offers`: requested/effective discount, baseline/offer price, remaining contribution, discount leakage per 1,000, extra purchases needed, whole-number requirement, required total probability and feasibility status.

Offer `status` is `feasible`, `nonpositive_margin`, or `exceeds_one_unit_limit`. `feasible` means mathematically possible under the given assumptions, not likely or proven profitable. Undefined thresholds are JSON `null`. Every top-level response also includes effective settings and interpretation notes.

See [the actual full response](../examples/response.json) for the exact field structure. Probabilities are separate binary co-purchase probabilities and do not need to sum to one.

## Use from Python

```python
from stories_promo.service import PromotionService

tool = PromotionService("artifacts/model.json")
result = tool.recommend({
    "anchor": "Iced Matcha",
    "branch": "Garden",
    "daypart": "afternoon",
    "weekday": "Tuesday",
    "order_type": "Dine-in",
    "available_products": ["Almond Croissant", "Blueberry Muffin"],
    "baseline_probability_overrides": {"Almond Croissant": 0.05},
    "operating_cost_per_opportunity": 0.01,
})
```

`PromotionService` is independent of HTTP and can be used by a notebook, UI backend or batch job. It reads only the artifact at inference time. It never reads future transactions, updates the model or mutates the artifact.

## UI integration

Fetch `/options` on startup and derive controls from the returned catalog. Send the selected context and scenario controls to `/recommend`. Display abstention explicitly, distinguish the probability proxy from a response forecast, and show unprofitable/impossible offers as such. The default policy and period are available in options metadata.

The included studio implements this flow. Product/context changes clear previous results until submitted again. Switching an alternative or discount uses the returned server-calculated data; no financial calculation is reimplemented in JavaScript.

The current adapter assumes same-origin or server-side requests. For a separate browser origin, configure a narrowly allowed origin in the future hosting layer. Authentication, live stock, live prices and event logging should be integrated before an operational trial.

## Command-line usage

```bash
python -m stories_promo options
python -m stories_promo recommend --request examples/request.json
python -m stories_promo recommend --request - < examples/request.json
python examples/run_demo.py
```

The demo regenerates the actual JSON response and a 54-row sensitivity table in `reports/example_sensitivity.csv`. These scenarios change assumptions; they are not further model fitting or test-set tuning.
