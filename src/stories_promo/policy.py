"""Training-only evidence, explicit eligibility rules, and affinity/margin ranking."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DataValidationError
from .economics import discounted_price


def build_evidence(train: pd.DataFrame, policy: dict) -> dict:
    products = sorted(train["product"].unique().tolist())
    indices = {product: i for i, product in enumerate(products)}
    pairs = np.zeros((len(products), len(products)), dtype=int)
    baskets = list(train.groupby("transaction_id"))
    standalone = np.zeros(len(products), dtype=int)
    for _, basket in baskets:
        found = [indices[p] for p in basket["product"].unique()]
        pairs[np.ix_(found, found)] += 1
        if len(found) == 1:
            standalone[found[0]] += 1
    catalog, branches = {}, {}
    for product, group in train.groupby("product", sort=True):
        category = str(group.category.iloc[0])
        if category not in policy["category_groups"]:
            raise DataValidationError(f"No compatibility group configured for category {category}")
        catalog[product] = {"category": category, "group": policy["category_groups"][category],
                            "basket_count": int(pairs[indices[product], indices[product]]),
                            "standalone_basket_count": int(standalone[indices[product]])}
    distinct = train.drop_duplicates(["transaction_id", "product"])
    for branch, group in train.groupby("branch", sort=True):
        branches[branch] = {}
        for product, rows in group.groupby("product", sort=True):
            if rows.price.nunique() != 1 or rows.cost.nunique() != 1:
                raise DataValidationError(f"Prices/costs vary in training for {branch}/{product}; explicit dated catalog needed")
            branches[branch][product] = {
                "price": float(rows.price.iloc[0]), "cost": float(rows.cost.iloc[0]),
                "basket_count": int(distinct.loc[(distinct.branch == branch) & (distinct["product"] == product)].shape[0]),
            }
        for category in {catalog[p]["category"] for p in branches[branch]}:
            members = [p for p in branches[branch] if catalog[p]["category"] == category]
            counts = pd.Series({p: branches[branch][p]["basket_count"] for p in members})
            for product, percentile in counts.rank(method="average", pct=True).items():
                branches[branch][product]["popularity_percentile"] = float(percentile)
    return {"products": products, "catalog": catalog, "branches": branches,
            "pair_baskets": pairs.tolist(), "total_baskets": len(baskets)}


def candidate_mask(examples: pd.DataFrame, evidence: dict, policy: dict,
                   max_popularity_percentile: float | None = None,
                   ranking_discount: float | None = None) -> np.ndarray:
    products = evidence["products"]
    rarity = policy["max_popularity_percentile"] if max_popularity_percentile is None else max_popularity_percentile
    discount = policy["ranking_discount"] if ranking_discount is None else ranking_discount
    pairs = np.asarray(evidence["pair_baskets"])
    lookup = {p: i for i, p in enumerate(products)}
    rows = []
    cache = {}
    for example in examples.itertuples(index=False):
        key = (example.anchor, example.branch)
        if key not in cache:
            eligible = np.zeros(len(products), dtype=bool)
            if example.anchor in lookup and example.branch in evidence["branches"]:
                anchor = evidence["catalog"][example.anchor]
                branch = evidence["branches"][example.branch]
                for j, candidate in enumerate(products):
                    item = evidence["catalog"][candidate]
                    local = branch.get(candidate)
                    eligible[j] = bool(
                        local and candidate != example.anchor and item["group"] != anchor["group"]
                        and pairs[lookup[example.anchor], j] >= policy["min_pair_baskets"]
                        and item["basket_count"] >= policy["min_product_baskets"]
                        and local["popularity_percentile"] <= rarity
                        and discounted_price(local["price"], discount) - local["cost"] > 0
                    )
            cache[key] = eligible
        rows.append(cache[key])
    return np.asarray(rows, dtype=bool)


def margin_matrix(examples: pd.DataFrame, evidence: dict, discount: float = 0.0) -> np.ndarray:
    return np.array([[discounted_price(evidence["branches"][branch][product]["price"], discount)
                      - evidence["branches"][branch][product]["cost"]
                      if product in evidence["branches"].get(branch, {}) else 0.0
                      for product in evidence["products"]] for branch in examples.branch])


def choose(probability: np.ndarray, mask: np.ndarray, margins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scores = np.where(mask, probability * margins, -np.inf)
    covered = mask.any(axis=1)
    # Sorted product order provides deterministic tie-breaking.
    selected = scores.argmax(axis=1)
    return selected, covered
