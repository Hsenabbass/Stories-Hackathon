import json
from pathlib import Path

import pytest

from stories_promo.data import load_data
from stories_promo.service import PromotionService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def dataset():
    return load_data(ROOT / "data/raw/stories_transactions.csv")


@pytest.fixture(scope="session")
def config():
    return json.loads((ROOT / "configs/default.json").read_text())


@pytest.fixture(scope="session")
def service():
    return PromotionService(ROOT / "artifacts/model.json")


@pytest.fixture
def request_payload():
    return json.loads((ROOT / "examples/request.json").read_text())
