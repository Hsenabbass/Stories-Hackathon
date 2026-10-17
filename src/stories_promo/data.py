"""Validate source records and create one reproducible masked basket per transaction."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


COLUMNS = {
    "Transaction ID": "transaction_id", "Date": "date", "Time": "time",
    "Branch": "branch", "Customer ID": "customer_id", "Order Type": "order_type",
    "Product": "product", "Category": "category", "Quantity": "quantity",
    "Unit Price (USD)": "price", "Discount Rate": "discount",
    "Unit Cost (USD)": "cost", "Line Revenue (USD)": "revenue",
    "Line Gross Profit (USD)": "gross_profit",
}
NUMERIC = ["quantity", "price", "discount", "cost", "revenue", "gross_profit"]
DAYPARTS = ("morning", "midday", "afternoon", "evening", "overnight")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class DataValidationError(ValueError):
    """The input cannot be interpreted without changing its meaning."""


def daypart(hour: int) -> str:
    if 7 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "midday"
    if 16 <= hour < 20:
        return "afternoon"
    if 20 <= hour < 24:
        return "evening"
    return "overnight"


def load_data(path: str | Path) -> tuple[pd.DataFrame, dict]:
    path = Path(path)
    raw = pd.read_csv(path, dtype={name: "string" for name in COLUMNS if name not in [
        "Quantity", "Unit Price (USD)", "Discount Rate", "Unit Cost (USD)",
        "Line Revenue (USD)", "Line Gross Profit (USD)",
    ]})
    missing = sorted(set(COLUMNS) - set(raw.columns))
    if missing:
        raise DataValidationError(f"Missing columns: {missing}")
    frame = raw.rename(columns=COLUMNS)[list(COLUMNS.values())].copy()
    trimmed = 0
    for column in set(frame.columns) - set(NUMERIC):
        original = frame[column]
        frame[column] = original.str.strip().replace("", pd.NA)
        trimmed += int((original.fillna("") != frame[column].fillna("")).sum())
    required = frame.drop(columns="customer_id")
    if required.isna().any().any():
        raise DataValidationError("Missing required values; fix the source rather than impute basket identities or economics.")
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[NUMERIC].to_numpy()).all():
        raise DataValidationError("Non-finite numeric values")
    valid = (
        (frame.quantity > 0) & (frame.quantity % 1 == 0) & (frame.price > 0)
        & (frame.cost >= 0) & frame.discount.between(0, 1, inclusive="left")
    )
    if not valid.all():
        raise DataValidationError("Invalid quantity, price, cost, or discount")
    frame["timestamp"] = pd.to_datetime(frame.date + " " + frame.time, format="%Y-%m-%d %H:%M:%S", errors="raise")
    if not frame.order_type.isin(["Dine-in", "Takeaway"]).all():
        raise DataValidationError("Unknown order type")
    consistency = frame.groupby("transaction_id")[["timestamp", "branch", "order_type"]].nunique()
    if (consistency > 1).any().any():
        raise DataValidationError("A transaction spans conflicting timestamps, branches, or order types")
    if (frame.groupby("product").category.nunique() > 1).any():
        raise DataValidationError("A product has conflicting categories")
    revenue_error = (frame.revenue - frame.quantity * frame.price * (1 - frame.discount)).abs()
    profit_error = (frame.gross_profit - (frame.revenue - frame.quantity * frame.cost)).abs()
    if (revenue_error > 0.011).any() or (profit_error > 0.011).any():
        raise DataValidationError("Revenue or gross profit fails reconciliation within $0.011 per line")
    frame["daypart"] = frame.timestamp.dt.hour.map(daypart)
    frame["weekday"] = frame.timestamp.dt.dayofweek.map(dict(enumerate(WEEKDAYS)))
    audit = {
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": len(frame), "transactions": int(frame.transaction_id.nunique()),
        "products": int(frame["product"].nunique()), "branches": sorted(frame.branch.unique().tolist()),
        "missing_customer_ids": int(frame.customer_id.isna().sum()),
        "identical_rows_retained": int(raw.duplicated().sum()),
        "repeated_transaction_product_rows": int(frame.duplicated(["transaction_id", "product"]).sum()),
        "trimmed_cells": trimmed, "rows_removed": 0,
        "max_revenue_reconciliation_error_usd": float(revenue_error.max()),
        "max_profit_reconciliation_error_usd": float(profit_error.max()),
        "first_date": str(frame.timestamp.min()), "last_date": str(frame.timestamp.max()),
        "interpretation": "Repeated lines retained; targets and evidence use distinct product presence. Customer ID excluded.",
    }
    return frame.sort_values(["timestamp", "transaction_id", "product"]).reset_index(drop=True), audit


def split_data(frame: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    bounds = [pd.Timestamp(config[k]) for k in ["train_start", "validation_start", "test_start", "test_end_exclusive"]]
    if not all(a < b for a, b in zip(bounds, bounds[1:])):
        raise DataValidationError("Split boundaries must be strictly increasing")
    if (frame.timestamp < bounds[0]).any() or (frame.timestamp >= bounds[-1]).any():
        raise DataValidationError("Source contains dates outside the configured study window")
    parts = {name: frame.loc[(frame.timestamp >= start) & (frame.timestamp < end)].copy()
             for name, start, end in zip(["train", "validation", "test"], bounds, bounds[1:])}
    if any(part.empty for part in parts.values()):
        raise DataValidationError("Each chronological split must contain transactions")
    return parts


def make_examples(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    rows = []
    for transaction_id, basket in frame.groupby("transaction_id", sort=True):
        products = sorted(basket["product"].unique())
        digest = hashlib.sha256(f"{seed}:{transaction_id}".encode()).digest()
        anchor = products[int.from_bytes(digest[:8], "big") % len(products)]
        first = basket.iloc[0]
        rows.append({
            "transaction_id": transaction_id, "date": first.timestamp.strftime("%Y-%m-%d"),
            "anchor": anchor, "branch": first.branch, "daypart": first.daypart,
            "weekday": first.weekday, "order_type": first.order_type,
            "targets": [p for p in products if p != anchor], "basket_size": len(products),
        })
    return pd.DataFrame(rows)


def target_matrix(examples: pd.DataFrame, products: list[str]) -> np.ndarray:
    lookup = {p: i for i, p in enumerate(products)}
    result = np.zeros((len(examples), len(products)), dtype=np.uint8)
    for row, targets in enumerate(examples.targets):
        for product in targets:
            if product in lookup:
                result[row, lookup[product]] = 1
    return result
