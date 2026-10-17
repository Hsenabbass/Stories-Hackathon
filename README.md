# Stories promotion opportunities

Identify an under-selling product that complements a given purchase, explain the historical evidence, and calculate how many additional purchases each discount must generate to break even.

**Team:** Hussein Abbas, Rabih Abdul Khalek, Hussein Zahwe.

The repository contains a trained model, three simple baselines, a reproducible chronological evaluation, a financial calculator, and a Python/JSON/HTTP interface ready for a UI. No training is required to try the included artifact.

## What the evidence says

May validation selected a regularized contextual logistic model with **C = 0.1**. On June's **6,906 transactions**, the fixed under-selling policy recommends on **3,959 opportunities (57.3%)**. Its historical basket-match rate is **1.41%**, versus **1.52%** for the popularity baselines. Context has slightly better probability loss, but **the paired intervals do not establish a recommendation improvement**. There is no measured sales or profit uplift.

For the selected policy, retrospective exposure implies **1.27** and **2.83 additional units per 1,000 covered opportunities** at 5% and 10% discounts, respectively, before operating costs or substitution. These are conditional accounting hurdles, not forecasts. A low hurdle does not establish that an offer will work.

Start with [the results](reports/RESULTS.md), [the experiment protocol](docs/experiment_protocol.md), and [methodology and limitations](docs/methodology.md). The model is kept because it won the prespecified May probability criterion, not because it beat every baseline on June.

## Try it

Use Python 3.12 (tested) or 3.13. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m stories_promo recommend --request examples/request.json
```

On Windows, activate with `.venv\Scripts\activate` instead. The provided workspace already has an installed `.venv`.

The example asks for an add-on to **Iced Matcha at Garden on Tuesday afternoon, dine-in**. Its first suggestion is **Almond Croissant**, supported by 40 training co-purchase baskets. The model's historical compatibility probability is 2.06%. Using that as a baseline scenario proxy, the 5% and 10% offers require approximately **2.62** and **6.02 additional purchases per 1,000 opportunities**, respectively. Whole-number thresholds round up. This is a plausibility suggestion; raw basket lift is below one, and the pairing evidence alone does not establish incremental demand.

Inspect [the example request](examples/request.json) and [complete response](examples/response.json). The response includes alternatives, support counts, within-category popularity, prices, margins, break-even thresholds, and assumptions. It can return an explicit abstention.

## Interactive API and future UI

```bash
python -m stories_promo serve
```

Open [the interactive API docs](http://127.0.0.1:8000/docs). Use `GET /options` to populate controls and `POST /recommend` to calculate offers. The server binds to localhost by default. It is a local prototype; external hosting and authentication are not configured.

Controls include anchor product, branch, daypart, weekday, dine-in/takeaway, model choice, number of alternatives, discounts, a ranking discount, a popularity limit, available products, existing basket items, baseline probability scenarios, operating cost, and substitution loss. [API contract and examples](docs/api.md) explain units and defaults.

## Reproduce and test

```bash
# Train on Jan–Apr and select on May; no June model scoring occurs here.
python -m stories_promo train

# Evaluate the frozen artifact on June; no fit or selection occurs here.
python -m stories_promo evaluate

# Or run both stages, then regenerate the concrete example and sensitivities.
python -m stories_promo reproduce
python examples/run_demo.py
python -m pytest
```

To preserve the shipped results during a new experiment:

```bash
python -m stories_promo reproduce --artifact artifacts/local/model.json --reports reports/local
```

Adjust [the configuration](configs/default.json) before training, not after inspecting June outcomes. The same seed, source, dependencies and configuration reproduce the selected model and metrics; small floating-point differences may occur across platforms. A full study runs locally without network access after installation. Tests also verify that changing June targets cannot change fitted models, evidence, or selection.

Verification completed: **31 passing tests**, a second full run with byte-identical model and evaluation reports, independent reconciliation of all 6,906 June prediction rows, and successful live HTTP checks. [Verification record](reports/verification.json) records the checks and the harmless dependency deprecation warning observed during tests.

## Repository map

| Location | Purpose |
| --- | --- |
| `src/stories_promo/` | Validation, training, baselines, eligibility, economics, evaluation, service, CLI and API |
| `configs/default.json` | Frozen split dates, grids, seed and policy rules |
| `data/raw/` | Original unmodified transaction CSV and data provenance |
| `artifacts/model.json` | Non-executable JSON containing all six selected family models, training evidence and provenance |
| `reports/RESULTS.md` | Human-readable evaluation with links to auditable outputs |
| `reports/*.json`, `reports/*.csv` | Audit, validation trials, metrics, calibration, per-transaction predictions, discount exposure and sensitivity |
| `examples/` | Ready-to-run request, actual response and sensitivity generator |
| `tests/` | Data integrity, split isolation, probability models, economics and API tests |
| `docs/` | Protocol, methodology, data contract, API contract and original hackathon brief |

The source files were moved into `data/raw/` and `docs/reference/` without changing their contents. Word's temporary lock file and local environments are ignored. No customer identity enters the model or reports.

## Scope and next decision

“Under-selling” means lower observed basket frequency than comparable products in the same branch/category. It does not prove unmet demand. Missing inventory, exposures, rejected offers and randomized discounts prevent estimating causal offer response. These records also lack purchase order, so evaluation is basket completion, not next-item prediction.

The useful next step is a small randomized trial of no suggestion, full-price suggestion, and the same suggestion at a specified discount, measuring total basket contribution per eligible opportunity. [The methodology](docs/methodology.md#pilot-design) specifies the needed logs, guardrails and decision rule.
