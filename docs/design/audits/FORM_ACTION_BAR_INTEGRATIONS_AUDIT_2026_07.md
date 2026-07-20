# Form Action Bar Integrations Audit — July 2026

## Scope

The audit reviewed form footer copy and action grouping across the Kubernetes, Prometheus, and Alertmanager integration workflows.

Reviewed templates:

- `cluster/partials/_form.html`;
- `prometheus/instance_form.html`;
- `prometheus/config.html`;
- `alertmanager/instance_form.html`;
- `alertmanager/partials/_detail_configuration.html`;
- `alertmanager/config.html`.

## Findings

Provider forms used different footer geometry and helper lengths. The Alertmanager registration footer contained a multi-stage explanation beside `Register Instance`, even though reachability and registration flow were already explained by the Endpoint & Access validation header and the Alertmanager Registration Flow.

The same duplication appeared in Prometheus and Alertmanager edit forms, where readiness-reset behavior was described as a long sentence beside the save action.

## Standard Introduced

A shared component was added:

```text
app/templates/components/form_action_bar.html
```

The standard limits footer helper copy to one concise sentence, normally 72 characters or fewer, and keeps detailed workflow information in the owning validation, flow, or evidence component.

## Implemented Copy

| Provider | Workspace | Helper |
|---|---|---|
| Kubernetes | Add Cluster | `Save to start Kubernetes inventory onboarding.` |
| Kubernetes | Edit Cluster | `Save changes to update cluster configuration.` |
| Prometheus | Register Connection | `Register now; validate from the connection detail.` |
| Prometheus | Edit Connection | `Save changes, then run Full Validation.` |
| Prometheus | Cluster Configuration | `Save changes, then run Full Validation.` |
| Alertmanager | Register Instance | `Register after Test Connection succeeds.` |
| Alertmanager | Edit Instance | `Save changes, then run Full Validation.` |
| Alertmanager | Instance Configuration | `Save changes, then run Full Validation.` |
| Alertmanager | Cluster Configuration | `Test changes before saving this configuration.` |

## Removed Long Copy

The following patterns were removed from action footers:

- explanations that registration remains disabled until reachability verification succeeds;
- multi-clause readiness reset explanations;
- broad statements covering connectivity, inventory, and observability mapping;
- repeated instructions already present in the Integration Flow or Connection Validation Header.

## Result

- Shared action-footer geometry: implemented.
- Alertmanager Register Instance helper shortened: implemented.
- Kubernetes, Prometheus, and Alertmanager coverage: implemented.
- Detailed workflow copy retained in contextual components: implemented.
- Accessibility labels for action regions: implemented.
- Automated guardrail: implemented.
