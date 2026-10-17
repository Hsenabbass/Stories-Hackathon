import pytest

from stories_promo.economics import break_even, discounted_price


def test_hand_calculated_break_even_with_menu_rounding():
    # $10 price, $4 cost, 10% discount, 5% baseline: $50 leakage / $5 margin = 10 purchases.
    result = break_even(10, 4, .05, .10)
    assert result["discount_exposure_per_1000_usd"] == 50
    assert result["additional_purchases_per_1000"] == pytest.approx(10)
    assert result["whole_additional_purchases_per_1000"] == 10
    assert result["required_total_purchase_probability"] == pytest.approx(.06)
    assert .06 * (9 - 4) - .05 * (10 - 4) == pytest.approx(0)
    assert discounted_price(3.95, .1) == 3.56


def test_costs_and_substitution_are_included():
    result = break_even(10, 4, .05, .1, operating_cost_per_opportunity=.02, substitution_loss_per_opportunity=.03)
    assert result["additional_purchases_per_1000"] == pytest.approx(20)


def test_preserves_existing_stronger_discount_without_stacking():
    result = break_even(10, 4, .05, .1, baseline_discount=.15)
    assert result["effective_discount"] == .15
    assert result["offer_price_usd"] == 8.5
    assert result["additional_purchases_per_1000"] == 0


def test_unprofitable_margin_and_impossible_probability():
    assert break_even(10, 9, .05, .2)["status"] == "nonpositive_margin"
    result = break_even(10, 8, .9, .1)
    assert result["status"] == "exceeds_one_unit_limit"
    assert not result["feasible_with_one_unit_limit"]


def test_zero_baseline_and_no_discount():
    result = break_even(10, 4, 0, 0)
    assert result["additional_purchases_per_1000"] == 0
    assert result["required_relative_increase"] is None


@pytest.mark.parametrize("values", [(10,4,float('nan'),.1), (10,4,-.1,.1), (10,4,.1,1), (-1,0,.1,0)])
def test_invalid_inputs(values):
    with pytest.raises(ValueError):
        break_even(*values)
