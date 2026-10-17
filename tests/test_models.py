import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from stories_promo.models import fit_model, predict


def test_pair_model_excludes_structural_anchor_zeros(config):
    x = pd.DataFrame({"anchor": ["A", "A", "B", "B"]})
    y = np.array([[0, 1], [0, 0], [1, 0], [0, 0]])
    model = fit_model("pair", x, y, ["A", "B"], 10, config)
    probabilities = predict(model, x)
    np.testing.assert_allclose(probabilities, [[0, .5], [0, .5], [.5, 0], [.5, 0]])


def test_logistic_serialized_prediction_matches_manual_design(config):
    x = pd.DataFrame({"anchor": ["A", "A", "B", "B", "C", "C"] * 10})
    y = np.tile([[0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]], (10, 1))
    model = fit_model("anchor_logistic", x, y, ["A", "B", "C"], .1, config)
    prediction = predict(model, pd.DataFrame({"anchor": ["A"]}))[0]
    index = model["feature_names"].index("anchor=A")
    expected = expit(np.array(model["weights"])[:, index] + np.array(model["intercepts"]))
    expected[0] = 0
    np.testing.assert_allclose(prediction, expected)
    assert all(name.startswith("anchor=") for name in model["feature_names"])


def test_unseen_context_baseline_backs_off(config):
    x = pd.DataFrame({"anchor": ["A", "B"], "branch": ["Known", "Known"], "daypart": ["morning", "morning"]})
    y = np.array([[0, 1], [1, 0]])
    model = fit_model("context_popularity", x, y, ["A", "B"], 10, config)
    x.loc[0, "branch"] = "Unknown"
    assert predict(model, x)[0, 1] == pytest.approx(model["prior"][1])
