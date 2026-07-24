# Import Resolution Hotfix

Date: 2026-07-24

## Scope

This hotfix makes the foundation patch self-contained when applied to an existing
KAORI working tree.

## Corrections

1. Adds `app/analytics/common/coercion.py`, which is imported by Capacity,
   Forecast, Storage, Top Consumers, and Workload analytics services.
2. Changes the integration runtime CLI to import the canonical monitoring module
   directly instead of importing a function through the runtime package façade.
3. Includes the canonical `runtime/monitoring.py` implementation so the dispatcher
   symbol is present even when earlier incremental patches were applied out of order.
4. Keeps `app/integrations/runtime/__init__.py` free of compatibility exports.
5. Adds behavior and architecture contract tests for the corrected boundaries.

## Validation

```bash
ruff check app tests scripts migrations
python -m compileall -q app tests scripts migrations
pytest -q tests/analytics/test_common_coercion.py
pytest -q tests/contracts/architecture/test_import_resolution_hotfix_contract.py
pytest -q -m "not debug"
```

## Rollback

Revert the hotfix commit. No migration or persistent-data rollback is required.

## Files Changed

- `app/analytics/common/coercion.py`
- `app/commands/integrations.py`
- `app/integrations/runtime/__init__.py`
- `app/integrations/runtime/monitoring.py`
- `tests/analytics/test_common_coercion.py`
- `tests/contracts/architecture/test_import_resolution_hotfix_contract.py`
- `docs/reviews/2026-07-24-import-resolution-hotfix.md`
