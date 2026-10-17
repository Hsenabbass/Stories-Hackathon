"""Evaluate the frozen artifact; this module never fits or selects a model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .data import load_data, make_examples, split_data, target_matrix
from .evaluation import evaluate, historical_economics, paired_day_bootstrap
from .models import predict
from .policy import candidate_mask, margin_matrix
from .training import write_json


def backtest(data_path: str | Path, artifact_path: str | Path, report_dir: str | Path) -> dict:
    artifact_path, report_dir = Path(artifact_path), Path(report_dir)
    bundle = json.loads(artifact_path.read_text())
    lines, audit = load_data(data_path)
    if audit["source_sha256"] != bundle["source_sha256"]:
        raise ValueError("Source hash differs from training. Reproduce against the original data or start a new study.")
    config, evidence = bundle["config"], bundle["evidence"]
    test = split_data(lines, config)["test"]
    products = evidence["products"]
    if set(test["product"]) - set(products):
        raise ValueError("Test contains an unseen product; extend the cold-start protocol before evaluating")
    # This study uses fixed catalog prices. Refuse an invalid economics comparison if that changes.
    for (branch, product), group in test.groupby(["branch", "product"]):
        local = evidence["branches"].get(branch, {}).get(product)
        if local is None or not (group.price.eq(local["price"]).all() and group.cost.eq(local["cost"]).all()):
            raise ValueError(f"June catalog drift at {branch}/{product}; dated economics required")
    examples = make_examples(test, config["seed"])
    y = target_matrix(examples, products)
    eligible = candidate_mask(examples, evidence, config["policy"])
    margins = margin_matrix(examples, evidence, config["policy"]["ranking_discount"])
    metrics, records, calibration = {}, {}, {}
    financial = []
    for name, model in bundle["models"].items():
        metrics[name], records[name], calibration[name] = evaluate(examples, y, predict(model, examples), products, eligible, margins)
        for row in historical_economics(records[name], test, evidence, config["policy"]["discount_options"]):
            financial.append({"model": name, **row})
    selected = bundle["selected_model"]
    comparison = {name: paired_day_bootstrap(records[selected], record, config["seed"])
                  for name, record in records.items() if name != selected}
    slices = []
    chosen_records = records[selected]
    for dimension in ["branch", "daypart", "order_type"]:
        for value, group in chosen_records.groupby(dimension):
            covered = group.loc[group.covered]
            slices.append({"dimension": dimension, "value": value, "opportunities": len(group),
                           "recommendations": len(covered), "hits": int(covered.hit.sum()),
                           "hit_rate": float(covered.hit.mean()) if len(covered) else None,
                           "mean_predicted_probability": float(covered.probability.mean()) if len(covered) else None})
    result = {
        "selected_model": selected, "selected_before_test": True,
        "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "source_sha256": audit["source_sha256"], "models": metrics,
        "selected_minus_comparators": comparison, "selected_model_slices": slices,
        "caveat": "Chronological backtest. This dataset had been explored in earlier discussion; June is not wholly untouched external confirmation. No causal uplift measured.",
    }
    write_json(report_dir / "test_metrics.json", result)
    write_json(report_dir / "calibration.json", calibration)
    pd.DataFrame(financial).to_csv(report_dir / "discount_exposure.csv", index=False)
    chosen_records.to_csv(report_dir / "test_predictions.csv", index=False)
    distribution = chosen_records.loc[chosen_records.covered].groupby(["branch", "recommended"]).agg(
        recommendations=("hit", "size"), historical_matches=("hit", "sum"), mean_probability=("probability", "mean"))
    distribution.to_csv(report_dir / "recommendation_distribution.csv")
    _write_report(report_dir, result, financial)
    print(f"June evaluation written to {report_dir}; frozen model: {selected}", flush=True)
    return result


def _write_report(report_dir: Path, result: dict, financial: list[dict]) -> None:
    selected = result["selected_model"]
    primary = result["models"][selected]
    report = ["# Evaluation results", "",
              f"May validation selected **{selected}** before June evaluation. June contains {primary['opportunities']:,} masked baskets; the fixed promotion policy covers {primary['recommendations']:,} ({primary['coverage']:.1%}).",
              "", "Each opportunity reveals one reproducibly sampled product from a completed basket. Single-product baskets remain in the denominator. A hit means the suggested product was also present, not that a customer accepted an offer.",
              "", "## Model comparison", "",
              "All policies use identical training-only candidate rules and full-price contribution ranking. Lower log loss/Brier is better. Hit rate is among covered opportunities.", "",
              "| Model | May selected | June policy hit rate | Eligible log loss | Eligible Brier | Mean predicted probability |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for name, score in result["models"].items():
        report.append(f"| {name} | {'Yes' if name == selected else ''} | {score['policy_hit_rate']:.2%} | {score['eligible_candidates']['log_loss']:.5f} | {score['eligible_candidates']['brier']:.5f} | {score['policy_mean_predicted_probability']:.2%} |")
    report += ["", "## Paired uncertainty", "",
               "Differences below are selected-model minus comparator hit rates, in percentage points. Intervals resample whole June days together across both policies (2,000 draws). They do not include model-fitting uncertainty, repeated customers across days, or future drift.", "",
               "| Comparator | Difference | 95% day-bootstrap interval |", "| --- | ---: | ---: |"]
    for name, comp in result["selected_minus_comparators"].items():
        low, high = comp["day_cluster_bootstrap95"]
        report.append(f"| {name} | {100 * comp['difference_in_hit_rate']:.2f} pp | [{100 * low:.2f}, {100 * high:.2f}] pp |")
    report += ["", "## Historical discount exposure", "",
               "One unit of the selected add-on per opportunity. Existing stronger discounts are preserved, never stacked. Requirements sum each offer's exposure divided by its own remaining margin; they assume extra purchases arise in those same offer groups. They are descriptive hurdles, not forecast sales or profit.", "",
               "| Requested discount | Extra discount on historical purchases | Required extra units per 1,000 covered opportunities |", "| ---: | ---: | ---: |"]
    for row in financial:
        if row["model"] == selected:
            amount = row["required_units_per_1000_eligible_opportunities"]
            report.append(f"| {row['discount']:.0%} | ${row['additional_discount_exposure_usd']:.2f} | {amount:.2f} |")
    report += ["", "## Interpretation and limits", "",
               "Model choice is based on May eligible-candidate log loss because the financial tool consumes probabilities. The June ranking does not change that choice. Compare the paired intervals before claiming any ranking improvement. Calibration bins and branch/daypart slices are available in the JSON reports.", "",
               "Under-selling means the lower half of observed training basket counts within the same branch and category. Missing inventory, footfall, offer impressions and counterfactual purchases prevent a claim of unmet demand or causal sales uplift. Source costs are assumed to approximate incremental costs. Operating costs and substitution are zero in the table and adjustable in the tool.", "",
               result["caveat"], "",
               "The executable protocol, assumptions, and proposed randomized test are in [methodology](../docs/methodology.md). Machine-readable results accompany this report."]
    (report_dir / "RESULTS.md").write_text("\n".join(report) + "\n")
