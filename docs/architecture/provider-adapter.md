# Provider Runtime Adapter Contract

A provider runtime adapter translates provider-specific behavior into the shared Integration Runtime Framework.

## Responsibilities

A provider adapter may:

- build a provider client from protected configuration;
- execute provider-specific validation;
- discover version and capabilities;
- map compatibility profiles;
- produce diagnostics;
- construct health factors; and
- return a shared runtime state.

It must not:

- render templates;
- read Flask request state;
- implement asset-domain analytics;
- duplicate shared health scoring or presentation logic;
- expose secrets; or
- create provider-specific runtime UI contracts.

## Minimum interface

Conceptually, an adapter provides:

```python
class RuntimeAdapter:
    provider: str

    def refresh(self, instance):
        """Run provider validation and return provider result data."""

    def get_state(self, instance, *, validation_result=None):
        """Translate persisted or fresh provider data into RuntimeState."""
```

The exact Python protocol may evolve, but consumer and UI code must rely on shared runtime contracts rather than provider implementation details.

## File placement

```text
app/<provider>/runtime_adapter.py
```

Examples:

```text
app/alertmanager/runtime_adapter.py
app/prometheus/runtime_adapter.py
app/harbor/runtime_adapter.py
app/vault/runtime_adapter.py
app/velero/runtime_adapter.py
```

## Adapter flow

```text
Provider instance
        ↓
Protected connection specification
        ↓
Provider validation and discovery
        ↓
Provider result
        ↓
Adapter translation
        ↓
Shared RuntimeState
```

## Security requirements

- Never include credentials in diagnostics or snapshots.
- Sanitize endpoints before presentation.
- Bound all network timeouts.
- Preserve specific authentication, TLS, transport, and API failure classes.
- Store only the minimum operational metadata required for diagnostics.

## Testing requirements

Every adapter should test:

- successful validation;
- authentication failure;
- transport or TLS failure;
- unsupported or partial capability discovery;
- readiness versus health separation;
- health-factor construction;
- secret-free diagnostic output; and
- state reconstruction from persisted observations without a live request.

## Metrics intermediary rule

A provider adapter must identify the runtime endpoint actually contacted by KAORI. For a Thanos Query URL, endpoint identity and version belong to Thanos. Backend Prometheus versions may be unknown. The adapter selects compatibility expectations from endpoint and administrator source-profile context, but feature readiness is determined only by probes against the exact configured endpoint.
