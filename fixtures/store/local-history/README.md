# HATE-P2-001 Local Store Fixture

This fixture documents the local `.hate` store shape used by P2. Tests create
the store under `tmp_path` so golden fixtures are not mutated during normal test
runs.

Expected generated files:

- `.hate/history-index.json`
- `.hate/runs/<run_id>/qeg-bundle.json`
- `.hate/runs/<run_id>/product-readiness-report.json`
- `.hate/runs/<run_id>/enterprise-risk-debt-register.json`
- `.hate/runs/<run_id>/store-manifest.json`
