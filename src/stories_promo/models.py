"""Small, auditable probabilistic models; persistence uses JSON, never pickle."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression


FEATURE_SETS = {
    "anchor_logistic": ["anchor"],
    "context_logistic": ["anchor", "branch", "daypart", "order_type"],
    "weekday_logistic": ["anchor", "branch", "daypart", "order_type", "weekday"],
}


def fit_model(name: str, examples: pd.DataFrame, y: np.ndarray, products: list[str],
              parameter: float, config: dict) -> dict:
    anchors = examples.anchor.to_numpy()
    valid = anchors[:, None] != np.array(products)[None, :]
    positives = y.sum(axis=0)
    denominators = valid.sum(axis=0)
    prior = (positives + 0.5) / (denominators + 1)
    model = {"name": name, "parameter": float(parameter), "products": products,
             "prior": prior.tolist()}
    if name in FEATURE_SETS:
        fields = FEATURE_SETS[name]
        encoder = DictVectorizer(sparse=True, sort=True)
        matrix = encoder.fit_transform(examples[fields].to_dict("records"))
        weights, intercepts, iterations = [], [], []
        for j, product in enumerate(products):
            mask = anchors != product
            target = y[mask, j]
            if len(np.unique(target)) < 2:
                weights.append(np.zeros(matrix.shape[1]).tolist())
                intercepts.append(float(np.log(prior[j] / (1 - prior[j]))))
                iterations.append(0)
                continue
            classifier = LogisticRegression(
                C=parameter, solver="lbfgs", penalty="l2", class_weight=None,
                max_iter=config["max_iter"], tol=config["tolerance"], random_state=config["seed"],
            )
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                classifier.fit(matrix[mask], target)
            weights.append(classifier.coef_[0].tolist())
            intercepts.append(float(classifier.intercept_[0]))
            iterations.append(int(classifier.n_iter_[0]))
        model.update(fields=fields, feature_names=encoder.get_feature_names_out().tolist(),
                     weights=weights, intercepts=intercepts, max_iterations_used=max(iterations))
    elif name in ("pair", "context_popularity", "global_popularity"):
        fields = {"pair": ["anchor"], "context_popularity": ["branch", "daypart"], "global_popularity": []}[name]
        groups = {}
        if fields:
            for key, indices in examples.groupby(fields, sort=True).indices.items():
                key = (key,) if isinstance(key, str) else key
                p = (y[indices].sum(axis=0) + parameter * prior) / (valid[indices].sum(axis=0) + parameter)
                groups["\u001f".join(key)] = p.tolist()
        model.update(fields=fields, groups=groups)
    else:
        raise ValueError(f"Unknown model: {name}")
    return model


def predict(model: dict, examples: pd.DataFrame) -> np.ndarray:
    if "weights" in model:
        # Reconstruct the documented one-hot vocabulary without deserializing executable objects.
        vocabulary = {name: i for i, name in enumerate(model["feature_names"])}
        matrix = np.zeros((len(examples), len(vocabulary)))
        for i, record in enumerate(examples[model["fields"]].to_dict("records")):
            for field, value in record.items():
                index = vocabulary.get(f"{field}={value}")
                if index is not None:
                    matrix[i, index] = 1
        probability = expit(matrix @ np.asarray(model["weights"]).T + np.asarray(model["intercepts"]))
    else:
        probability = np.tile(model["prior"], (len(examples), 1))
        for i, record in enumerate(examples[model["fields"]].to_dict("records")):
            key = "\u001f".join(record[field] for field in model["fields"])
            if key in model["groups"]:
                probability[i] = model["groups"][key]
    for j, product in enumerate(model["products"]):
        probability[examples.anchor.to_numpy() == product, j] = 0.0
    return probability
