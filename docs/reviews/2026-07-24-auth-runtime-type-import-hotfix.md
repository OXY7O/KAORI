# Authentication and Runtime Import Hotfix — 2026-07-24

## Scope

- Narrow untrusted browser SSO session values before numeric conversion so Pyright does not permit broad `object` coercion.
- Move `refresh_and_record()` into the canonical `app.integrations.runtime.refresh` module.
- Retire the thin `app.integrations.runtime.service` boundary and reject future imports to it.
- Add behavior and architecture regression coverage.

## Runtime boundary

`app.integrations.validation.tasks` now imports `refresh_and_record` from `app.integrations.runtime.refresh`. The refresh module owns provider refresh plus persistence, while `runtime.monitoring` remains the fan-out dispatcher. No import path returns from validation tasks to monitoring.

## Validation

Run `bash scripts/quality_gate.sh --all` in the KAORI Dev Container.
