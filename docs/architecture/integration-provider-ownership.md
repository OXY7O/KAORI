# Integration Provider Ownership

## Decision

KAORI keeps Prometheus and Alertmanager as two-layer modules inside the modular monolith:

```text
app/prometheus/                  HTTP routes, forms, registration, workspace presentation
app/integrations/prometheus/     provider transport, runtime, compatibility, binding operations

app/alertmanager/                HTTP routes, forms, registration, workspace presentation
app/integrations/alertmanager/   provider transport, runtime, normalization, binding operations
```

The dependency direction is one way:

```text
web/domain facade
    → Integration Registry
        → provider adapter
            → provider runtime/binding implementation
```

Canonical provider packages must never import their corresponding web/domain packages.

## Provider-Owned Operations

### Prometheus

| Operation | Ownership | Execution |
|---|---|---|
| `client.build` | scoped/unscoped Prometheus-compatible client | inline |
| `connection.test` | draft or persisted endpoint identity test | inline |
| `query_profile.audit` | PromQL feature-contract audit | integration validation queue |
| `runtime.validate` | full compatibility, query, metric, and retention validation | integration validation queue |
| `runtime.health` | lightweight endpoint health observation | integration runtime queue |
| `runtime.state` | provider evidence to shared runtime state | inline |
| `binding.create` | provider-neutral scope binding creation | inline |
| `binding.selector.update` | selector invalidation and update | inline |
| `binding.validate` | scoped Kubernetes metric identity probes | integration validation queue |

### Alertmanager

| Operation | Ownership | Execution |
|---|---|---|
| `client.build` | Alertmanager API v2 client | inline |
| `runtime.validate` | API, compatibility, and capability validation | integration validation queue |
| `runtime.health` | lightweight status endpoint observation | integration runtime queue |
| `runtime.state` | provider evidence to shared runtime state | inline |
| `binding.create` | provider-neutral scope binding creation | inline |
| `binding.selector.update` | selector invalidation and update | inline |
| `binding.validate` | scoped alert-filter validation | integration validation queue |

## Form Boundary

WTForms remain in the web/domain layer. Routes and domain facades convert form fields into provider-neutral keyword arguments before calling the Integration Registry. Provider modules do not import form classes.

## Transaction Boundary

Provider binding operations own their database commit/rollback behavior through the `commit` argument. Higher-level orchestration may pass `commit=False` when one transaction spans provider registration and initial binding creation.

Runtime validation owns persistence of provider evidence because the evidence schema is provider-specific. Shared runtime observation persistence remains in the integration runtime foundation.

## Guardrails

The architecture verifier and contract tests enforce:

- no `app.integrations.prometheus` import from `app.prometheus`;
- no `app.integrations.alertmanager` import from `app.alertmanager`;
- no provider-domain/form import from `app/integrations/binding_service.py`;
- registry operation declarations for runtime and binding lifecycle;
- no return of binding validation logic to domain service modules.

## Remaining Work

This batch does not move web routes, forms, or workspace presentation. Remaining reverse edges are tracked in the architecture debt ledger and include:

- integration landing-page presentation importing provider-domain presentation;
- Kubernetes adapter importing cluster/inventory application functions;
- cluster coverage resolving provider domains directly;
- provider source resolvers remaining in web/domain packages.

Those edges should be removed in separate commits with characterization tests before package movement.
