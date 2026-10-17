"""Generate a real recommendation and one-candidate sensitivity table."""

import csv
import json
from pathlib import Path

from stories_promo.economics import break_even
from stories_promo.service import PromotionService


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    service = PromotionService(root / "artifacts/model.json")
    request = json.loads((root / "examples/request.json").read_text())
    response = service.recommend(request)
    (root / "examples/response.json").write_text(json.dumps(response, indent=2, allow_nan=False) + "\n")
    if not response["recommendations"]:
        raise ValueError("Demo query abstained; inspect its constraints")
    candidate = response["recommendations"][0]
    item = service.evidence["branches"][request["branch"]][candidate["product"]]
    rows = []
    for multiplier in [.5, 1, 2]:
        for operating_cost in [0, .01, .03]:
            for substitution_loss in [0, .02]:
                for discount in [0, .05, .1]:
                    q = min(1, candidate["historical_copurchase_probability"] * multiplier)
                    offer = break_even(item["price"], item["cost"], q, discount,
                                       operating_cost_per_opportunity=operating_cost,
                                       substitution_loss_per_opportunity=substitution_loss)
                    rows.append({"anchor": request["anchor"], "branch": request["branch"],
                                 "candidate": candidate["product"], "baseline_probability_multiplier": multiplier,
                                 **offer})
    with (root / "reports/example_sensitivity.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {candidate['product']} example and {len(rows)} assumption scenarios")


if __name__ == "__main__":
    main()
