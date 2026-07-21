# KAORI Integration Kernel

`app/integrations` is KAORI's provider-neutral integration kernel. It gives the
core a small, stable API while provider implementation remains isolated.

```text
Route → Domain Service → Integration Registry → Adapter → External System
```

## Rules

- Cross-domain callers resolve integrations with `get_integration()` or
  `execute_integration_operation()`.
- Provider clients and compatibility logic live under
  `app/integrations/<provider>/`.
- UI/domain packages may contain forms, route handlers, presentation builders,
  and provider-specific business workflow, but they must not duplicate clients,
  adapters, credentials, bindings, or runtime persistence.
- Every asynchronous operation uses `JobExecution` and an explicitly mapped
  queue.
- Every provider declares capability keys and compatibility profiles.
- SQLAlchemy models remain centralized under `app/models/`.
- Old bookmark support is GET-only redirect logic in `legacy_routes.py`.

## Shared contracts

- `contracts/base.py`: runtime and operation adapter protocols.
- `contracts/capabilities.py`: capability declarations and evidence contract.
- `contracts/results.py`: provider-neutral runtime and operation results.
- `contracts/exceptions.py`: stable orchestration exceptions.
- `registry.py`: registration, lookup, dispatch, model loading, and queue map.

## Validation levels

1. **Test Connection** verifies submitted endpoint identity and reachability.
2. **Full Capability Validation** rebuilds compatibility, capabilities, and
   technical evidence using `integration-validation` workers.
3. **Scope Binding Validation** proves that a registered source can serve the
   selected operational scope and persists selector/evidence state.
4. **Runtime Refresh** performs lightweight health observation using
   `integration-runtime` workers.

See `docs/architecture/integration-module-map.md` and the README inside each
provider module.
