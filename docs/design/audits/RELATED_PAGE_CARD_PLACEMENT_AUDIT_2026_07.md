# Related Page Card Placement Audit — July 2026

## Scope

The audit reviewed Related Page Card placement in Roles & Access and all Kubernetes, Prometheus, and Alertmanager integration pages.

## Finding

The first implementation placed Related Page Cards on provider landing and registry pages. Those pages already act as navigation hubs and portfolio summaries, so the card duplicated page-level navigation without enough workflow context.

The action also had no guaranteed spacing from the content above when the card height was constrained.

## Placement Decision

Related Page Cards belong on contextual subpages such as create, edit, detail, configuration, validation, or workflow workspaces. They do not belong on overview, landing, list, or registry pages.

Exception: a single-page module such as Roles & Access may use the component on its main page because no separate workflow subpage exists.

## Implementation

Removed from:

```text
app/templates/integrations/kubernetes.html
app/templates/integrations/prometheus.html
app/templates/integrations/alertmanager.html
```

Applied to contextual subpages:

### Kubernetes

- cluster registration;
- cluster edit;
- Kubernetes connection detail.

Destination: `Kubernetes Inventory`.

### Prometheus

- reusable connection registration and edit;
- reusable connection detail;
- cluster-bound configuration.

Destination: `Kubernetes Analytics`.

### Alertmanager

- instance registration;
- cluster-bound configuration;
- instance configuration detail.

Destination: `Alert Intelligence`.

### Exception retained

- Roles & Access → Permission Catalog.

## Spacing Correction

The shared card now wraps its action in:

```text
mt-auto pt-6
```

This preserves the bottom-aligned action while guaranteeing 24 px separation from the description or authority boundary above.

## Result

- Landing and registry placements removed: implemented.
- Contextual subpage placements added: implemented.
- Single-page exception retained: implemented.
- Action spacing corrected: implemented.
- Guardrail test updated: implemented.
