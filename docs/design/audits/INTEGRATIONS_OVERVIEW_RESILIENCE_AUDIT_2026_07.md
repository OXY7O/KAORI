# Integrations Overview Resilience Audit — July 2026

## Scope

Reviewed the complete `/integrations/` landing-page path:

- route context construction;
- provider catalog aggregation;
- runtime aggregation;
- runtime row navigation;
- zero-integration rendering;
- filtered zero-result rendering;
- coverage categories;
- HTMX refresh behavior;
- domain documentation and regression tests.

## Incident

The page raised `werkzeug.routing.exceptions.BuildError` while rendering a Prometheus runtime row because the template called:

```jinja
url_for(row.detail_endpoint, **row.detail_kwargs)
```

A stale or malformed row referenced `prometheus.configuration` without the required `cluster_id`. One bad navigation contract therefore made the entire Integrations landing page unavailable.

## Findings

### 1. Dynamic route execution in the template

Runtime rows controlled both the Flask endpoint name and its arguments. This created an unnecessary hard dependency between presentation data and route signatures.

### 2. Prometheus overview counts depended on Kubernetes resolution

The overview built Prometheus rows by iterating Kubernetes clusters and resolving a source for each cluster. This excluded unbound Prometheus instances and made overview aggregation depend on Kubernetes inventory.

### 3. Alertmanager overview aggregation used cluster source resolution

The landing page imported the Alertmanager resolver even though it only needed registered instance counts and persisted runtime state.

### 4. Empty runtime state looked like a filtered result

With no integrations, the runtime table displayed the same message used for filters returning no rows. The state did not explain that zero integrations is a valid onboarding condition.

### 5. Coverage omitted Compute & Infrastructure

Kubernetes appeared in the Provider Catalog but had no corresponding domain coverage card.

### 6. Documentation had conflicting boundaries

One section described the overview as catalog-only while another documented a shared runtime table. The page contract was ambiguous.

## Implementation

### Provider-independent aggregation

`build_integrations_overview()` now loads persisted Kubernetes connections, Prometheus instances, and Alertmanager instances independently. It does not call provider resolvers or live endpoints.

Prometheus and Alertmanager instances no longer require a Kubernetes binding to be counted or displayed.

### Explicit runtime navigation

The runtime template maps supported providers to canonical detail routes:

- `integrations.kubernetes_detail` with `cluster_id`;
- `prometheus.instance_detail` with `instance_id`;
- `alertmanager.instance_detail` with `instance_id`.

Unknown or incomplete rows render `Unavailable`. Dynamic `url_for(row.detail_endpoint, **row.detail_kwargs)` is prohibited.

### Zero-state behavior

When no targets exist, Runtime Overview renders a dedicated `No Runtime Targets Yet` state. It does not render filters, table, or pagination. Provider Catalog and coverage remain available.

When filters return zero rows while targets exist, the table renders `No Runtime Targets Match These Filters` and retains the standard result footer.

### Coverage correction

Coverage now contains:

1. Compute & Infrastructure;
2. Observability;
3. Storage;
4. Security.

### Documentation correction

`docs/modules/integrations/UI_REFERENCE.md` and `app/integrations/README.md` now define a single consistent overview boundary and dependency contract.

## Required Boundary

The page may depend on the KAORI application schema and registered routes. It must not depend on:

- an external provider being reachable;
- any integration being registered;
- Kubernetes clusters existing;
- Prometheus or Alertmanager bindings existing;
- a primary source resolution;
- capability evidence or runtime observations existing.

## Validation Contract

Regression tests must confirm:

- dynamic runtime endpoints are absent;
- explicit canonical routes are present;
- provider aggregation is independent;
- zero-target and filtered-zero states are distinct;
- Compute & Infrastructure coverage is present;
- documentation records the persistence-only boundary.
