"""Reproduce descriptive discount evidence; never fit or select a model.

Run from the repository root: python examples/audit_discounts.py
Counts retain source rows. Product frequency uses distinct transaction IDs.
"""
import json
from pathlib import Path

from stories_promo.data import load_data

frame, audit = load_data('data/raw/stories_transactions.csv')
output = {'source_sha256': audit['source_sha256'], 'purpose': 'Descriptive evidence only; not a causal effect or model-selection input.', 'periods': {}}
for name, rows in [('training_jan_apr', frame[frame.timestamp < '2026-05-01']), ('full_jan_jun', frame)]:
    discounted = rows[rows.discount.eq(0.15)]
    frequency = rows.groupby('product').transaction_id.nunique()
    products = []
    for product, group in discounted.groupby('product'):
        products.append({'product': product, 'discounted_line_records': len(group), 'all_distinct_baskets': int(frequency[product])})
    output['periods'][name] = {
        'discounted_line_records': len(discounted),
        'distinct_discounted_transactions': int(discounted.transaction_id.nunique()),
        'branches': discounted.branch.value_counts().to_dict(),
        'categories': discounted.category.value_counts().to_dict(),
        'products': products,
    }
path = Path('reports/discount_observation.json')
path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
print(path)
