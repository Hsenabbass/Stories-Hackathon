import json

import pandas as pd

from stories_promo.training import train


def test_changing_june_targets_does_not_change_fit_or_selection(tmp_path, config):
    # A small complete study exercises the real pipeline, not mocked fit calls.
    rows = []
    patterns = [["Coffee", "Cake"], ["Coffee"], ["Tea", "Muffin"], ["Tea"],
                ["Cake"], ["Muffin"], ["Coffee", "Muffin"], ["Tea", "Cake"]]
    for month in [1, 5, 6]:
        for number in range(32):
            for product in patterns[number % len(patterns)]:
                rows.append({"Transaction ID": f"{month}-{number}", "Date": f"2026-{month:02d}-01", "Time": "09:30:00",
                             "Branch": "Garden", "Customer ID": None, "Order Type": "Dine-in", "Product": product,
                             "Category": "Hot Coffee" if product in ["Coffee", "Tea"] else "Bakery", "Quantity": 1,
                             "Unit Price (USD)": 3, "Discount Rate": 0, "Unit Cost (USD)": 1,
                             "Line Revenue (USD)": 3, "Line Gross Profit (USD)": 2})
    frame = pd.DataFrame(rows)
    config = json.loads(json.dumps(config))
    config["regularization_c"], config["smoothing_alpha"] = [.1], [50]
    config["policy"].update(min_pair_baskets=1, min_product_baskets=1, max_popularity_percentile=1)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    source = tmp_path / "data.csv"
    frame.to_csv(source, index=False)
    first = train(source, config_path, tmp_path / "first.json", tmp_path / "reports1")
    june_cake = (frame.Date == "2026-06-01") & (frame.Product == "Cake")
    frame.loc[june_cake, "Product"] = "Muffin"
    frame.to_csv(source, index=False)
    second = train(source, config_path, tmp_path / "second.json", tmp_path / "reports2")
    assert first["source_sha256"] != second["source_sha256"]
    assert first["models"] == second["models"]
    assert first["evidence"] == second["evidence"]
    assert first["selected_model"] == second["selected_model"]
