# Runtime Refresh Symbol Resolution

## Scope

This change hardens the import boundary between integration validation tasks and the canonical runtime refresh implementation.

## Problem

Some KAORI working copies contained the earlier `app.integrations.runtime.refresh` implementation, which exported only `refresh_runtime` and `get_runtime_state`. Validation tasks then referenced `refresh_and_record`, causing static analyzers to report an unknown import symbol even though the runtime refresh module itself was resolvable.

## Resolution

- `app.integrations.runtime.refresh` explicitly exports `refresh_runtime`, `get_runtime_state`, and `refresh_and_record`.
- Validation tasks import the runtime refresh module as `runtime_refresh` and call `runtime_refresh.refresh_and_record(...)`.
- The boundary remains acyclic: runtime refresh persists through the runtime repository and never imports validation tasks.
- Contract tests verify function ownership, the module-level import pattern, and the canonical public API.

## Validation

```bash
python -m ruff check app migrations tests scripts
python -m ruff format --check app migrations tests scripts
python -m pyright --project pyrightconfig.json
pytest -q tests/contracts/architecture/test_runtime_monitoring_import_boundary_contract.py
bash scripts/quality_gate.sh --all
```

## Rollback

Revert all files in this change together. Do not restore `app.integrations.runtime.service`; that compatibility boundary remains retired.

## Files Changed

- `app/integrations/runtime/refresh.py`
- `app/integrations/validation/tasks.py`
- `tests/contracts/architecture/test_runtime_monitoring_import_boundary_contract.py`
- `docs/reviews/2026-07-24-runtime-refresh-symbol-resolution.md`
