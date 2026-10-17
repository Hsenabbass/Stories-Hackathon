# Stories: better add-on decisions

**Team:** Hussein Abbas, Rabih Abdel Khalek, Husein Zahweh.

Stories needs a practical way to give lower-selling products more opportunities without unnecessarily discounting purchases that would happen anyway. Given a customer's product and shopping context, this tool recommends a plausible lower-frequency complement, explains its historical support, and compares the additional purchases needed to pay for an optional discount.

**Deliverable:** a trained recommendation service, simple comparison baselines, a chronological evaluation, a contribution-based financial calculator, and a working staff UI. It is a business decision-support prototype, not a demonstrated sales-uplift model. The included artifact runs without retraining.

## Reviewer reading order

1. This README: problem, outcome, operation and repository navigation.
2. [Methodology and design decisions](docs/methodology.md): the 15% promotion observation, cleaning, feature choices, learning, recommendation rules, evaluation and economics.
3. [Frozen experiment protocol](docs/experiment_protocol.md), then [evaluation results](reports/RESULTS.md): what was selected, what was tested, and what the evidence supports.
4. [Data contract](docs/data_contract.md): source fields, validation rules, redundancy and reproducible audit.
5. [Staff workflow](docs/ui.md) and [API contract](docs/api.md): how to operate and integrate the tool.

For code review, follow `data.py → models.py → training.py → policy.py → economics.py → service.py`; `evaluation.py` and `backtest.py` implement the independent evaluation. Tests cover those boundaries.

## Business reasoning and honest result

The observed 15% discounts included frequently bought products, notably Iced Latte. All 504 such source line records occur at Harbour in Cold Coffee or Desserts. This suggests a question worth testing: **could Stories spend promotional margin on a suitable quieter product instead?** It does not prove the historical promotions were wasteful. See the [verified observation and its design consequences](docs/methodology.md#the-15-discount-observation-and-its-design-consequences).

May selected contextual logistic regression with **C = 0.1** using eligible-candidate probability log loss. On June's **6,906 baskets**, the fixed policy covers **3,959 opportunities (57.3%)**. Its historical match rate is **1.41% (56 matches)**, compared with **1.52% (60 matches)** for popularity baselines. Paired uncertainty intervals do not establish an improvement. We report that result rather than switching models or tuning thresholds after inspecting June.

A match means the suggested item was present in the historical basket. It is **not an accepted offer, an additional sale or profit uplift**. The product's value is making the suggestion and its financial hurdle explicit, ready for a prospective business test.

## Install and run

Use Python 3.12 (tested) or 3.13. Run commands from this repository's root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m stories_promo serve
```

On Windows use `.venv\Scripts\activate`. The supplied workspace already has an installed `.venv`. If port 8000 is occupied, use `python -m stories_promo serve --port 8001`.

Open [the staff tool](http://127.0.0.1:8000/). The UI and API run together; no frontend build, Node installation or external assets are required.

1. **Order:** search a product; select branch, daypart, weekday and dine-in/takeaway.
2. **Add-on:** choose a recommendation. “Out of stock” requests alternatives; “Why this pairing?” opens concise supporting evidence.
3. **Offer:** keep **0% / no discount**, or compare **10%, 20%, 30%, 40% or 50%**. Prices, contribution feasibility and break-even requirements come from the backend. A high discount may be unviable; availability in the menu is not an endorsement.
4. **New order:** clear the current product and results while retaining context. Stock exclusions last until branch change or page reload.

On narrow screens, the three stages are separate steps. Statistical detail is available on demand, not on the main staff screen. The UI does not submit an order to a POS, track acceptance or apply a live discount. Historical prices and costs need confirmation before operational use.

## Programmatic use and discount versions

```bash
python -m stories_promo recommend --request examples/request.json
python -m stories_promo options
```

[The saved example](examples/response.json) pairs Iced Matcha with Almond Croissant at Garden, Tuesday afternoon. It records 40 training co-purchase baskets. The 10% offer is $4.37 and requires about **6.02 extra purchases per 1,000 matching opportunities**, rounded up to **7 whole purchases**, under the stated baseline assumptions. That is a hurdle, not a forecast.

The **frozen experiment, artifact defaults and original CLI example compare 0%, 5% and 10%**. The **staff UI explicitly requests 0%–50% in ten-point steps and initially selects 0%**. This is an interface scenario expansion, not a retraining or evaluation change. The June results have not been rewritten to imply that 20%–50% offers were evaluated. Pass `"discounts": [0, 0.1, 0.2, 0.3, 0.4, 0.5]` in an API/CLI request to match the UI.

[Interactive API documentation](http://127.0.0.1:8000/docs) exposes advanced scenarios: existing discounts, operating costs, substitution loss, baseline-probability overrides, inventory, known basket exclusions, model comparisons and candidate limits. See [request fields and units](docs/api.md). API discounts are fractions, not whole percentages.

## Reproduce, verify and extend

```bash
# Fit Jan–Apr; select with May only.
python -m stories_promo train
# Evaluate the saved, frozen artifact on June.
python -m stories_promo evaluate
# Reproduce both stages without overwriting the shipped study.
python -m stories_promo reproduce --artifact artifacts/local/model.json --reports reports/local
# Reproduce the example/sensitivity table and descriptive 15% audit.
python examples/run_demo.py
python examples/audit_discounts.py
python -m pytest
```

Training/evaluation without output overrides regenerate the shipped paths. Model reproduction does not regenerate this README or the explanatory docs. `run_demo.py` regenerates the original 0%/5%/10% example and 54-row sensitivity table. The discount audit only describes source observations; it does not fit models.

The suite currently has **32 passing tests**. [Original model verification](reports/verification.json) records the earlier 31-test run, byte-identical reproduction and independent reconciliation of all 6,906 June rows. [UI verification](reports/ui_verification.json) records the later 32-test suite and browser checks. These records refer to different stages, not conflicting evaluation results.

For future experiments, set changes before evaluation and use a new untouched future period. Additional tuning should use forward validation within historical training/development data, not repeated optimization against June. The supplied June backtest was preceded by full-dataset exploration and is not pristine external confirmation.

## Repository navigation

| Location | What to inspect |
| --- | --- |
| `data/raw/stories_transactions.csv` | Original, unchanged line-level transactions; provenance in `data/raw/README.md` |
| `docs/reference/` | Original hackathon brief |
| `configs/default.json` | Split dates, seed, regularization/smoothing grids and frozen candidate policy |
| `src/stories_promo/data.py` | Validation, basket construction, deterministic masking and split boundaries |
| `src/stories_promo/models.py`, `training.py` | Three baselines, three logistic feature families, fitting and May selection |
| `src/stories_promo/policy.py` | Training support, branch/category rarity, compatibility and ranking rules |
| `src/stories_promo/economics.py` | Rounded prices, existing-discount handling and financial feasibility |
| `src/stories_promo/evaluation.py`, `backtest.py` | Metrics, uncertainty and frozen June evaluation |
| `src/stories_promo/service.py`, `api.py`, `cli.py` | Shared inference contract, HTTP endpoints and command-line entry points |
| `src/stories_promo/web/` | Buildless staff UI; presentation and requests only |
| `artifacts/model.json` | Ordinary JSON weights, counts, catalogs, selected models and source provenance |
| `reports/data_audit.json`, `discount_observation.json` | Cleaning outcomes and reproducible descriptive 15% evidence |
| `reports/validation.json`, `test_metrics.json`, `calibration.json` | Parameter trials, final comparisons and calibration |
| `reports/test_predictions.csv`, `discount_exposure.csv` | Auditable per-transaction predictions and historical discount exposure |
| `reports/RESULTS.md` | Human-readable frozen study results |
| `examples/` | Concrete requests/responses and reproducible supporting analyses |
| `tests/` | Data validation, leakage isolation, model, economics and service checks |

## What Stories should do next

Run a small, prospectively designed randomized pilot comparing no suggestion, a full-price suggestion, and the same suggestion with a fixed discount. Measure **total basket contribution per eligible opportunity**, including implementation costs and substitution, rather than only add-on units. Log rejected offers and stock availability as well as purchases. Scale only when the result supports a worthwhile contribution gain. [Pilot design and required logs](docs/methodology.md#pilot-design) explain how.
