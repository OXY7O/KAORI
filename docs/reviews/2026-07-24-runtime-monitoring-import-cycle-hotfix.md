# Runtime Monitoring Import-Cycle Hotfix

## Problem

`app.integrations.validation.tasks` imported `refresh_and_record` from
`app.integrations.runtime.monitoring`, while the monitoring module imported
`enqueue_runtime_refresh` from the validation task module. Importing either side during
pytest collection could therefore observe a partially initialized module.

## Resolution

- `app.integrations.runtime.monitoring` now owns only provider fan-out and queue dispatch.
- `app.integrations.runtime.service` owns the synchronous refresh-and-persist operation.
- `app.integrations.validation.tasks` imports `refresh_and_record` from the runtime service.
- The CLI and periodic Celery entrypoint continue to use the canonical monitoring dispatcher.
- An architecture contract prevents the bidirectional import from returning.

## Validation

Run:

```bash
python -m compileall -q app tests scripts migrations
pytest -q tests/contracts/architecture/test_runtime_monitoring_import_boundary_contract.py
pytest -q tests/integrations/test_delete_admission_serialization.py
ruff check app tests scripts migrations
```
