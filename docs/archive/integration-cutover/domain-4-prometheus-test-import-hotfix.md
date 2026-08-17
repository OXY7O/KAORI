# Domain 4 Prometheus Test Import Hotfix

## Change

Removed the unused `pytest` and `PrometheusError` imports from
`tests/prometheus/test_capability_aware_source_selection.py`.

## Reason

The imports were not used by either functional test and caused Ruff F401 failures.
No production behavior or test coverage changed.

## Validation

```bash
ruff check tests/prometheus/test_capability_aware_source_selection.py
pytest -q tests/prometheus/test_capability_aware_source_selection.py
bash scripts/quality_gate.sh
```

## Rollback

Revert this patch commit. There is no database or runtime rollback requirement.
