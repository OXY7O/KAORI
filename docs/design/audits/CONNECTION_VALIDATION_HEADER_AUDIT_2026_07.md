# Connection Validation Header Audit — July 2026

## Scope

The audit reviewed validation and refresh action headers across the Kubernetes, Prometheus, and Alertmanager integration workspaces.

Reviewed areas:

- Kubernetes connection detail runtime workspace;
- Prometheus connection detail validation workspace;
- Prometheus cluster-bound validation workspace;
- Alertmanager registration endpoint workspace;
- Alertmanager instance capability validation workspace.

## Findings

Connection action headers used different icon sizes, padding, helper lengths, breakpoints, and action alignment. The Alertmanager registration helper also explained API behavior in more detail than required beside `Test Connection`.

## Implementation

A shared component was added:

```text
app/templates/components/connection_validation_header.html
```

Applied to:

| Provider | Workspace | Standardized Helper |
|---|---|---|
| Kubernetes | Runtime Health & Diagnostics | `Refresh connection health and compatibility evidence.` |
| Prometheus | Connection validation | `Test reachability, then rebuild capability evidence.` |
| Prometheus | Cluster-bound validation | `Test reachability, then rebuild metrics readiness evidence.` |
| Alertmanager | Endpoint & Access | `Validate endpoint access before registration.` |
| Alertmanager | Capability matrix | `Rebuild capability and readiness evidence.` |

The Alertmanager `Test Connection` action was moved into the `Endpoint & Access` header so the action and its immediate purpose remain one visual unit. The footer now contains only the save or registration action.

## Result

- Shared geometry: implemented.
- Helper copy reduced to one concise sentence: implemented.
- Kubernetes, Prometheus, and Alertmanager coverage: implemented.
- Detailed workflow information retained outside the header: implemented.
- Guardrail test: implemented.
