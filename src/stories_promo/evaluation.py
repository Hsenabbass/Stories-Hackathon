"""Comparable basket-completion metrics and descriptive historical discount exposure."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .economics import break_even
from .policy import choose


def binary_scores(y: np.ndarray, p: np.ndarray, mask: np.ndarray) -> dict:
    actual = y[mask].astype(float)
    predicted = np.clip(p[mask], 1e-9, 1 - 1e-9)
    if not len(actual):
        return {"log_loss": None, "brier": None, "candidate_decisions": 0}
    return {"log_loss": float(-np.mean(actual * np.log(predicted) + (1 - actual) * np.log1p(-predicted))),
            "brier": float(np.mean((actual - predicted) ** 2)), "candidate_decisions": len(actual)}


def wilson_interval(successes: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    p, z = successes / n, 1.959963984540054
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - width, center + width]


def evaluate(examples: pd.DataFrame, y: np.ndarray, probability: np.ndarray, products: list[str],
             eligible: np.ndarray, margins: np.ndarray) -> tuple[dict, pd.DataFrame, list[dict]]:
    selected, covered = choose(probability, eligible, margins)
    rows = np.arange(len(examples))
    hits = y[rows, selected].astype(bool) & covered
    q = probability[rows, selected]
    nonanchor = examples.anchor.to_numpy()[:, None] != np.array(products)[None, :]
    unrestricted = np.where(nonanchor, probability, -np.inf).argmax(axis=1)
    multi = y.sum(axis=1) > 0
    n_covered = int(covered.sum())
    score = {
        "opportunities": len(examples), "recommendations": n_covered,
        "coverage": float(covered.mean()), "policy_hits": int(hits.sum()),
        "policy_hit_rate": float(hits[covered].mean()) if n_covered else None,
        "policy_hit_rate_wilson95": wilson_interval(int(hits.sum()), n_covered),
        "hits_per_1000_all_opportunities": float(1000 * hits.mean()),
        "policy_mean_predicted_probability": float(q[covered].mean()) if n_covered else None,
        "policy_brier": float(np.mean((hits[covered] - q[covered]) ** 2)) if n_covered else None,
        "policy_hit_rate_multi_product_baskets": float(hits[covered & multi].mean()) if (covered & multi).any() else None,
        "unrestricted_top1_hit_rate": float(y[rows, unrestricted].mean()),
        "single_product_fraction": float((~multi).mean()),
        "all_nonanchor": binary_scores(y, probability, nonanchor),
        "eligible_candidates": binary_scores(y, probability, eligible),
    }
    calibration = []
    # Fixed bins; no test-dependent quantile boundaries.
    edges = [0, .01, .02, .04, .06, .08, .1, .15, .25, .5, 1.000001]
    ece = 0.0
    for lower, upper in zip(edges, edges[1:]):
        member = covered & (q >= lower) & (q < upper)
        n = int(member.sum())
        if n:
            predicted, observed = float(q[member].mean()), float(hits[member].mean())
            ece += n * abs(predicted - observed) / max(n_covered, 1)
            calibration.append({"lower": lower, "upper": min(upper, 1.0), "count": n,
                                "mean_predicted": predicted, "observed": observed})
    score["policy_ece_fixed_bins"] = ece if n_covered else None
    records = examples[["transaction_id", "date", "anchor", "branch", "daypart", "weekday", "order_type", "basket_size"]].copy()
    records["recommended"] = [products[j] if flag else None for j, flag in zip(selected, covered)]
    records["covered"] = covered
    records["hit"] = hits
    records["probability"] = np.where(covered, q, np.nan)
    return score, records, calibration


def paired_day_bootstrap(left: pd.DataFrame, right: pd.DataFrame, seed: int, repetitions: int = 2000) -> dict:
    if not left.transaction_id.equals(right.transaction_id) or not left.covered.equals(right.covered):
        raise ValueError("Paired comparison requires identical opportunities and coverage")
    daily = pd.DataFrame({"date": left.date, "delta": left.hit.astype(int) - right.hit.astype(int),
                          "covered": left.covered.astype(int)}).groupby("date").sum()
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(daily), size=(repetitions, len(daily)))
    denominator = daily.covered.to_numpy()[draws].sum(axis=1)
    numerator = daily.delta.to_numpy()[draws].sum(axis=1)
    usable = denominator > 0
    difference = numerator[usable] / denominator[usable]
    return {"difference_in_hit_rate": float(daily.delta.sum() / daily.covered.sum()) if daily.covered.sum() else None,
            "day_cluster_bootstrap95": np.quantile(difference, [.025, .975]).tolist() if len(difference) else None,
            "days": len(daily), "repetitions": repetitions,
            "interpretation": "Paired descriptive uncertainty within this month; not causal uplift or training uncertainty."}


def historical_economics(records: pd.DataFrame, lines: pd.DataFrame, evidence: dict,
                         discounts: list[float]) -> list[dict]:
    existing = lines.groupby(["transaction_id", "product"]).discount.max().to_dict()
    output = []
    offered = records.loc[records.covered]
    for discount in discounts:
        exposure, required, impossible = 0.0, 0.0, 0
        for row in offered.itertuples(index=False):
            item = evidence["branches"][row.branch][row.recommended]
            baseline_discount = float(existing.get((row.transaction_id, row.recommended), 0))
            result = break_even(item["price"], item["cost"], float(row.hit), discount,
                                baseline_discount=baseline_discount)
            exposure += result["discount_exposure_per_1000_usd"] / 1000
            if result["additional_purchases_per_1000"] is None:
                impossible += 1
            else:
                required += result["additional_purchases_per_1000"] / 1000
        output.append({
            "discount": discount, "eligible_opportunities": len(offered), "all_opportunities": len(records),
            "historical_matches": int(offered.hit.sum()), "additional_discount_exposure_usd": exposure,
            "sum_offer_specific_required_additional_units": required if not impossible else None,
            "required_units_per_1000_eligible_opportunities": 1000 * required / len(offered) if len(offered) and not impossible else None,
            "required_units_per_1000_all_opportunities": 1000 * required / len(records) if not impossible else None,
            "nonpositive_margin_offers": impossible,
            "interpretation": "Descriptive one-unit discount exposure on observed matches; offer-specific costs divided by respective margins. No observed promotion effect.",
        })
    return output
