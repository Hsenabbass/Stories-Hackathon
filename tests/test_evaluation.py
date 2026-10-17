import numpy as np
import pandas as pd
import pytest

from stories_promo.evaluation import evaluate, historical_economics, paired_day_bootstrap


def test_single_product_baskets_count_as_misses_and_abstentions_are_not_hits():
    x = pd.DataFrame({"transaction_id": ["a", "b", "c"], "date": ["2026-06-01"] * 3,
                      "anchor": ["A"] * 3, "branch": ["Garden"] * 3, "daypart": ["morning"] * 3,
                      "weekday": ["Monday"] * 3, "order_type": ["Dine-in"] * 3, "basket_size": [2, 1, 2]})
    y = np.array([[0, 1], [0, 0], [0, 1]])
    p = np.tile([0, .4], (3, 1))
    mask = np.array([[False, True], [False, True], [False, False]])
    metrics, records, _ = evaluate(x, y, p, ["A", "B"], mask, np.ones_like(p))
    assert metrics["policy_hit_rate"] == .5
    assert metrics["coverage"] == pytest.approx(2 / 3)
    assert metrics["hits_per_1000_all_opportunities"] == pytest.approx(1000 / 3)
    assert not records.hit.iloc[2]
    assert paired_day_bootstrap(records, records, 490)["day_cluster_bootstrap95"] == [0, 0]


def test_historical_exposure_protects_existing_discount_and_counts_one_unit():
    records = pd.DataFrame({"transaction_id": ["a", "b"], "branch": ["Garden"] * 2,
                            "recommended": ["B"] * 2, "covered": [True, True], "hit": [True, True]})
    lines = pd.DataFrame({"transaction_id": ["a", "a", "b"], "product": ["B"] * 3, "discount": [.15, .15, 0]})
    evidence = {"branches": {"Garden": {"B": {"price": 10, "cost": 4}}}}
    result = historical_economics(records, lines, evidence, [.1])[0]
    assert result["additional_discount_exposure_usd"] == 1
    assert result["sum_offer_specific_required_additional_units"] == pytest.approx(.2)
