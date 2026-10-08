# Validation record

The final artifact passed notebook/schema checks and all seven synthetic replay tests. The [final check log](validation_report.json) records the scope and review environment. The HTML preview contains all 13 figures and the full consolidated table.

Scope:

- Validate notebook JSON/schema and parse every Python cell.
- Check English source/stream text, absent saved exceptions, and empty pending-experiment outputs.
- Verify the 12 original PNG payload hashes and saved performance-table consistency.
- Exercise replay/accounting, confirmation and missing-data mechanics on small synthetic fixtures.
- Render the notebook to read-only HTML and inspect the new metric overview.

The original market CSV files were not attached. Full-SPY replay, API download, model retraining, pending experimental profitability, and hosted GitHub Actions execution are not claimed.

The offline workflow follows the official action usage documented at https://github.com/actions/checkout and https://github.com/actions/setup-python.
