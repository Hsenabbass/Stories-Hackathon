"""Conditional contribution accounting for one offered add-on unit per opportunity."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP


def discounted_price(price: float, discount: float) -> float:
    return float((Decimal(str(price)) * (1 - Decimal(str(discount)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def break_even(price: float, cost: float, baseline_probability: float, discount: float,
               baseline_discount: float = 0.0, operating_cost_per_opportunity: float = 0.0,
               substitution_loss_per_opportunity: float = 0.0) -> dict:
    values = [price, cost, baseline_probability, discount, baseline_discount,
              operating_cost_per_opportunity, substitution_loss_per_opportunity]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Economics inputs must be finite")
    if price <= 0 or cost < 0 or not 0 <= baseline_probability <= 1:
        raise ValueError("Invalid price, cost, or baseline probability")
    if not 0 <= discount < 1 or not 0 <= baseline_discount < 1:
        raise ValueError("Discounts must be between zero and one, excluding one")
    if operating_cost_per_opportunity < 0 or substitution_loss_per_opportunity < 0:
        raise ValueError("Additional costs and losses cannot be negative")
    effective = max(discount, baseline_discount)
    base_price = discounted_price(price, baseline_discount)
    offer_price = discounted_price(price, effective)
    margin = offer_price - cost
    exposure = baseline_probability * (base_price - offer_price)
    additional_cost = operating_cost_per_opportunity + substitution_loss_per_opportunity
    result = {
        "requested_discount": discount, "effective_discount": effective,
        "baseline_discount": baseline_discount, "baseline_purchase_probability": baseline_probability,
        "regular_price_usd": price, "baseline_price_usd": base_price,
        "offer_price_usd": offer_price, "unit_cost_usd": cost,
        "contribution_per_additional_unit_usd": round(margin, 6),
        "discount_exposure_per_1000_usd": round(1000 * exposure, 6),
        "operating_cost_per_opportunity_usd": operating_cost_per_opportunity,
        "substitution_loss_per_opportunity_usd": substitution_loss_per_opportunity,
        "additional_purchases_per_1000": None, "whole_additional_purchases_per_1000": None,
        "required_total_purchase_probability": None, "required_relative_increase": None,
        "status": "nonpositive_margin", "feasible_with_one_unit_limit": False,
    }
    if margin <= 0:
        return result
    increase = (exposure + additional_cost) / margin
    result.update(
        additional_purchases_per_1000=1000 * increase,
        whole_additional_purchases_per_1000=math.ceil(1000 * increase - 1e-10),
        required_total_purchase_probability=baseline_probability + increase,
        required_relative_increase=increase / baseline_probability if baseline_probability else None,
        status="feasible" if baseline_probability + increase <= 1 + 1e-12 else "exceeds_one_unit_limit",
        feasible_with_one_unit_limit=baseline_probability + increase <= 1 + 1e-12,
    )
    return result
