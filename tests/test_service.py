import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from stories_promo.api import create_app
from stories_promo.service import RecommendationRequest

from conftest import ROOT


def test_recommendation_contract_and_evidence(service, request_payload):
    response = service.recommend(request_payload)
    assert response["status"] == "recommended"
    assert response["recommendations"]
    for item in response["recommendations"]:
        assert item["product"] != request_payload["anchor"]
        assert item["evidence"]["training_pair_baskets"] >= 20
        assert item["evidence"]["within_branch_category_popularity_percentile"] <= .5
        assert [offer["requested_discount"] for offer in item["offers"]] == [0, .05, .1]
    json.dumps(response, allow_nan=False)


def test_empty_inventory_abstains_and_existing_items_excluded(service, request_payload):
    assert service.recommend({**request_payload, "available_products": []})["status"] == "abstained"
    first = service.recommend(request_payload)["recommendations"][0]["product"]
    response = service.recommend({**request_payload, "already_in_basket": [first]})
    assert first not in [x["product"] for x in response["recommendations"]]


def test_baseline_override_changes_economics_only(service, request_payload):
    original = service.recommend(request_payload)["recommendations"][0]
    changed = service.recommend({**request_payload, "baseline_probability_overrides": {original["product"]: .5}})["recommendations"][0]
    assert original["product"] == changed["product"]
    assert original["historical_copurchase_probability"] == changed["historical_copurchase_probability"]
    assert changed["offers"][-1]["baseline_purchase_probability"] == .5
    assert changed["economics_baseline_source"] == "user_scenario"


@pytest.mark.parametrize("change", [{"discounts": [1]}, {"discounts": [float('nan')]}, {"top_k": 0}, {"daypart": "noon"}, {"unexpected": True}])
def test_request_validation(request_payload, change):
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate({**request_payload, **change})


def test_api_smoke_and_unknown_values(request_payload):
    with TestClient(create_app(ROOT / "artifacts/model.json")) as client:
        assert client.get("/health").status_code == 200
        assert "products" in client.get("/options").json()
        assert client.post("/recommend", json=request_payload).json()["status"] == "recommended"
        assert client.post("/recommend", json={**request_payload, "branch": "Missing"}).status_code == 422
        assert client.post("/recommend", json={**request_payload, "anchor": "Unknown"}).status_code == 422
        assert client.get("/openapi.json").status_code == 200


def test_studio_and_packaged_assets_are_served_without_shadowing_api():
    with TestClient(create_app(ROOT / "artifacts/model.json")) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert 'id="context-form"' in page.text
        assert page.headers["cache-control"] == "no-cache"
        for asset in ["styles.css", "app.js", "favicon.svg"]:
            response = client.get(f"/assets/{asset}")
            assert response.status_code == 200
            assert response.content
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/options").json()["default_model"]
