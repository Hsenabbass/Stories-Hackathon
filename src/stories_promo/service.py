"""Framework-independent inference service with validated UI-friendly options."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .data import DAYPARTS, WEEKDAYS
from .economics import break_even
from .models import predict
from .policy import candidate_mask, margin_matrix


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    anchor: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    daypart: Literal["morning", "midday", "afternoon", "evening", "overnight"]
    weekday: Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    order_type: Literal["Dine-in", "Takeaway"]
    model: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)
    discounts: list[float] | None = Field(default=None, min_length=1, max_length=10)
    ranking_discount: float | None = Field(default=None, ge=0, lt=1)
    baseline_discount: float = Field(default=0.0, ge=0, lt=1)
    max_popularity_percentile: float | None = Field(default=None, gt=0, le=1)
    available_products: list[str] | None = None
    already_in_basket: list[str] = Field(default_factory=list)
    baseline_probability_overrides: dict[str, float] = Field(default_factory=dict)
    operating_cost_per_opportunity: float = Field(default=0.0, ge=0)
    substitution_loss_per_opportunity: float = Field(default=0.0, ge=0)

    @field_validator("discounts")
    @classmethod
    def check_discounts(cls, values: list[float] | None) -> list[float] | None:
        if values is None:
            return values
        if any(not np.isfinite(value) or not 0 <= value < 1 for value in values):
            raise ValueError("Discounts must be finite fractions in [0, 1)")
        return sorted(set(values))

    @field_validator("baseline_probability_overrides")
    @classmethod
    def check_probabilities(cls, values: dict[str, float]) -> dict[str, float]:
        if any(not np.isfinite(value) or not 0 <= value <= 1 for value in values.values()):
            raise ValueError("Baseline probabilities must be finite fractions in [0, 1]")
        return values


class PromotionService:
    def __init__(self, artifact_path: str | Path):
        self.bundle = json.loads(Path(artifact_path).read_text())
        if self.bundle.get("schema_version") != 1:
            raise ValueError("Unsupported artifact schema version")
        self.evidence = self.bundle["evidence"]
        self.products = self.evidence["products"]
        self.policy = self.bundle["config"]["policy"]

    def options(self) -> dict:
        return {
            "schema_version": 1, "default_model": self.bundle["selected_model"],
            "models": list(self.bundle["models"]), "products": self.products,
            "branches": {branch: sorted(items) for branch, items in self.evidence["branches"].items()},
            "dayparts": list(DAYPARTS), "weekdays": list(WEEKDAYS), "order_types": ["Dine-in", "Takeaway"],
            "daypart_hours": {"morning": "07:00–10:59", "midday": "11:00–15:59", "afternoon": "16:00–19:59", "evening": "20:00–23:59", "overnight": "00:00–06:59"},
            "default_policy": self.policy, "metadata": self.bundle["metadata"],
        }

    def recommend(self, request: RecommendationRequest | dict) -> dict:
        request = request if isinstance(request, RecommendationRequest) else RecommendationRequest.model_validate(request)
        settings = request.model_dump()
        for key, policy_key in [("discounts", "discount_options"), ("ranking_discount", "ranking_discount"),
                                ("max_popularity_percentile", "max_popularity_percentile")]:
            if settings[key] is None:
                settings[key] = self.policy[policy_key]
        request = RecommendationRequest.model_validate(settings)
        model_name = request.model or self.bundle["selected_model"]
        if model_name not in self.bundle["models"]:
            raise ValueError(f"Unknown model: {model_name}")
        if request.branch not in self.evidence["branches"]:
            raise ValueError(f"Unknown branch: {request.branch}")
        local = self.evidence["branches"][request.branch]
        if request.anchor not in local:
            raise ValueError(f"Anchor is not in the training catalog for {request.branch}")
        mentioned = set(request.already_in_basket) | set(request.available_products or []) | set(request.baseline_probability_overrides)
        unknown = mentioned - set(local)
        if unknown:
            raise ValueError(f"Products absent from this branch's training catalog: {sorted(unknown)}")
        example = pd.DataFrame([{"anchor": request.anchor, "branch": request.branch, "daypart": request.daypart,
                                 "weekday": request.weekday, "order_type": request.order_type}])
        effective_ranking_discount = max(request.ranking_discount, request.baseline_discount)
        mask = candidate_mask(example, self.evidence, self.policy, request.max_popularity_percentile, effective_ranking_discount)[0]
        for i, product in enumerate(self.products):
            if product in request.already_in_basket or (request.available_products is not None and product not in request.available_products):
                mask[i] = False
        model = self.bundle["models"][model_name]
        probability = predict(model, example)[0]
        margins = margin_matrix(example, self.evidence, effective_ranking_discount)[0]
        scores = probability * margins
        selected = sorted(np.flatnonzero(mask), key=lambda i: (-scores[i], self.products[i]))[:request.top_k]
        notes = [
            "Compatibility probabilities describe historical completed baskets under a mix of promotions; they are not measured offer acceptance or a no-offer causal baseline.",
            "Break-even calculations assume one offered unit per opportunity and recorded cost as incremental cost. Positive gains require demand above the threshold.",
            "Options are alternative offers, not a bundle of simultaneous recommendations.",
        ]
        if request.available_products is None:
            notes.append("Availability was not supplied; the training catalog is used, not live inventory.")
        if request.already_in_basket:
            notes.append("Other known basket items are excluded from candidates; probabilities condition on the anchor only, plus the selected model's context.")
        if request.max_popularity_percentile > self.policy["max_popularity_percentile"]:
            notes.append("Popularity limit is broader than the evaluated under-selling policy.")
        if request.daypart == "overnight":
            notes.append("Overnight has no support in this dataset; predictions use available model features or smoothed fallback.")
        if request.baseline_probability_overrides:
            notes.append("User-supplied baseline probabilities affect economics only; compatibility ranking remains model-based.")
        recommendations = []
        anchor_index = self.products.index(request.anchor)
        anchor_count = self.evidence["catalog"][request.anchor]["basket_count"]
        for i in selected:
            product = self.products[i]
            item, catalog = local[product], self.evidence["catalog"][product]
            count = self.evidence["pair_baskets"][anchor_index][i]
            conditional = count / anchor_count
            base_rate = catalog["basket_count"] / self.evidence["total_baskets"]
            q = request.baseline_probability_overrides.get(product, float(probability[i]))
            offers = [break_even(item["price"], item["cost"], q, discount, request.baseline_discount,
                                 request.operating_cost_per_opportunity, request.substitution_loss_per_opportunity)
                      for discount in request.discounts]
            recommendations.append({
                "product": product, "category": catalog["category"],
                "historical_copurchase_probability": float(probability[i]),
                "affinity_margin_score": float(scores[i]),
                "economics_baseline_source": "user_scenario" if product in request.baseline_probability_overrides else "historical_probability_proxy",
                "evidence": {"training_pair_baskets": count, "training_anchor_baskets": anchor_count,
                             "training_candidate_baskets": catalog["basket_count"],
                             "training_standalone_candidate_baskets": catalog["standalone_basket_count"],
                             "raw_pair_conditional_frequency": conditional,
                             "raw_basket_lift": conditional / base_rate,
                             "branch_candidate_baskets": item["basket_count"],
                             "within_branch_category_popularity_percentile": item["popularity_percentile"],
                             "compatibility_rule": "opposite food/drink group with minimum historical pair support"},
                "offers": offers,
            })
        return {"schema_version": 1, "status": "recommended" if recommendations else "abstained",
                "abstention_reason": None if recommendations else "No candidates satisfy compatibility, support, popularity, availability, basket exclusion, and positive ranking-margin rules.",
                "model": model_name, "context": example.iloc[0].to_dict(),
                "effective_options": request.model_dump(exclude={"anchor", "branch", "daypart", "weekday", "order_type", "model"}),
                "eligible_candidate_count": int(mask.sum()), "recommendations": recommendations, "notes": notes}
