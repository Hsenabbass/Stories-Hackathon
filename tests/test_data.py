import pandas as pd
import pytest

from stories_promo.data import COLUMNS, DataValidationError, load_data, make_examples, split_data, target_matrix


def test_audit_and_disjoint_chronological_splits(dataset, config):
    frame, audit = dataset
    assert audit["rows"] == 51177
    assert audit["transactions"] == 33887
    assert audit["identical_rows_retained"] == 132
    assert audit["rows_removed"] == 0
    parts = split_data(frame, config)
    ids = {key: set(part.transaction_id) for key, part in parts.items()}
    assert not (ids["train"] & ids["validation"] or ids["train"] & ids["test"] or ids["validation"] & ids["test"])
    assert parts["train"].timestamp.max() < parts["validation"].timestamp.min() < parts["test"].timestamp.min()


def test_anchor_independent_of_row_order_and_duplicate_lines(dataset):
    frame = dataset[0].iloc[:100]
    original = make_examples(frame, 490)
    shuffled = make_examples(frame.sample(frac=1, random_state=9), 490)
    repeated = make_examples(pd.concat([frame, frame]), 490)
    pd.testing.assert_frame_equal(original, shuffled)
    pd.testing.assert_frame_equal(original, repeated)
    assert all(row.anchor not in row.targets for row in original.itertuples())
    assert (target_matrix(original, sorted(frame["product"].unique())).sum(axis=1) == original.basket_size - 1).all()
    assert (original.basket_size == 1).any()


@pytest.mark.parametrize("column,value", [("Quantity", 0), ("Unit Price (USD)", -1), ("Discount Rate", 1), ("Line Revenue (USD)", 100)])
def test_invalid_economics_fails_loudly(tmp_path, dataset, column, value):
    raw = dataset[0].iloc[:3][list(COLUMNS.values())].rename(columns={v: k for k, v in COLUMNS.items()}).copy()
    raw.loc[raw.index[0], column] = value
    path = tmp_path / "bad.csv"
    raw.to_csv(path, index=False)
    with pytest.raises(DataValidationError):
        load_data(path)


def test_conflicting_transaction_metadata_rejected(tmp_path, dataset):
    row = dataset[0].iloc[[0]][list(COLUMNS.values())].rename(columns={v: k for k, v in COLUMNS.items()})
    raw = pd.concat([row, row], ignore_index=True)
    raw.loc[1, "Branch"] = "Conflicting branch"
    path = tmp_path / "conflict.csv"
    raw.to_csv(path, index=False)
    with pytest.raises(DataValidationError, match="conflicting"):
        load_data(path)
