# Original source data

`stories_transactions.csv` is the original supplied transaction file, moved here without alteration. It contains 51,177 lines describing 33,887 completed baskets from January through June 2026. The authoritative fingerprint and validation counts are in `reports/data_audit.json` and `artifacts/model.json` at the repository root.

Do not overwrite this file to clean it. Validation and preparation run in memory, and a new input should use a new filename with an explicit CLI `--data` argument and a matching experiment configuration. See `docs/data_contract.md` for required columns and interpretation.
