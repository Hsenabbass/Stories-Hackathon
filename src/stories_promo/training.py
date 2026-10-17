"""Fit on training data and select using validation data only."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import numpy as np

from .data import load_data, make_examples, split_data, target_matrix
from .evaluation import evaluate
from .models import fit_model, predict
from .policy import build_evidence, candidate_mask, margin_matrix


FAMILIES = ["global_popularity", "context_popularity", "pair", "anchor_logistic", "context_logistic", "weekday_logistic"]


def write_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def train(data_path: str | Path, config_path: str | Path, artifact_path: str | Path,
          report_dir: str | Path) -> dict:
    config = json.loads(Path(config_path).read_text())
    lines, audit = load_data(data_path)
    splits = split_data(lines, config)
    evidence = build_evidence(splits["train"], config["policy"])
    products = evidence["products"]
    examples = {name: make_examples(splits[name], config["seed"]) for name in ["train", "validation"]}
    for name in ["train", "validation"]:
        unseen = set(splits[name]["product"]) - set(products)
        if unseen:
            raise ValueError(f"{name} has products outside the training catalog: {sorted(unseen)}")
    targets = {name: target_matrix(part, products) for name, part in examples.items()}
    eligible = candidate_mask(examples["validation"], evidence, config["policy"])
    if not eligible.any():
        raise ValueError("No validation candidates satisfy the configured policy")
    margins = margin_matrix(examples["validation"], evidence, config["policy"]["ranking_discount"])
    trials, models, winners = [], {}, []
    for family in FAMILIES:
        grid = [1.0] if family == "global_popularity" else (
            config["regularization_c"] if family.endswith("logistic") else config["smoothing_alpha"])
        best = None
        for parameter in grid:
            print(f"Training {family}, parameter={parameter}", flush=True)
            model = fit_model(family, examples["train"], targets["train"], products, parameter, config)
            probability = predict(model, examples["validation"])
            metrics, _, _ = evaluate(examples["validation"], targets["validation"], probability, products, eligible, margins)
            trial = {"model": family, "parameter": parameter, "metrics": metrics}
            trials.append(trial)
            loss = metrics["eligible_candidates"]["log_loss"]
            if best is None or loss < best[0]:
                best = (loss, model, trial)
        models[family] = best[1]
        winners.append(best[2])
    # Ties retain the simpler, earlier family. No June metric is computed here.
    winner = min(winners, key=lambda x: x["metrics"]["eligible_candidates"]["log_loss"])
    split_summary = {}
    for name, part in splits.items():
        split_summary[name] = {"rows": len(part), "transactions": int(part.transaction_id.nunique()),
                               "first_date": part.timestamp.min().strftime("%Y-%m-%d"),
                               "last_date": part.timestamp.max().strftime("%Y-%m-%d")}
    audit["splits"] = split_summary
    source_code = {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                   for file in sorted(Path(__file__).parent.glob("*.py"))}
    bundle = {
        "schema_version": 1, "selected_model": winner["model"], "config": config,
        "source_sha256": audit["source_sha256"], "evidence": evidence, "models": models,
        "metadata": {"python": platform.python_version(),
                     "packages": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scikit-learn", "scipy"]},
                     "training_period": split_summary["train"], "validation_period": split_summary["validation"],
                     "source_code_sha256": source_code,
                     "selection_metric": "May mean binary log loss on the fixed eligible candidate set; smaller is better",
                     "probability_meaning": "Historical masked-basket co-purchase frequency under mixed observed promotions, not offer acceptance or causal response"},
    }
    report_dir = Path(report_dir)
    write_json(Path(artifact_path), bundle)
    write_json(report_dir / "data_audit.json", audit)
    write_json(report_dir / "validation.json", {"selected_model": winner["model"],
               "selection_metric": bundle["metadata"]["selection_metric"], "family_winners": winners, "trials": trials})
    print(f"Selected using May only: {winner['model']}", flush=True)
    return bundle
