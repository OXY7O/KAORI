# KAORI Foundation Readiness Review

## Decision

KAORI uses one canonical integration path:

`Route → Domain Service → Integration Registry → Provider Adapter → External Runtime`

Compatibility facades and legacy HTTP redirects are removed. New code must not
construct provider transports outside `app/integrations/<provider>/`.

## Persistence Authority

- `Cluster` owns Kubernetes asset identity and non-provider operational facts.
- `KubernetesConnection` owns Kubernetes endpoint, credentials, TLS policy,
  detected version/platform, compatibility, readiness, discovery, and validation evidence.
- `IntegrationInstance` owns provider-neutral lifecycle and runtime summary.
- `IntegrationBinding` owns provider-to-asset scope.
- `IntegrationRuntimeObservation` owns immutable runtime evidence history.

Provider runtime fields must not be copied back onto `Cluster`.

## Template Structure

Feature templates follow:

```text
app/templates/<domain>/<workspace>.html
app/templates/<domain>/<workspace>/partials/_*.html
app/templates/components/<category>/_*.html
```

Use `components/` only for reusable visual contracts used by more than one
workspace or domain. Domain-specific content remains beside its owning page with
an informative filename. Avoid generic names such as `_content.html`, `_card.html`,
or `_section.html` when the business meaning can be named directly.

## Technical-Debt Gates

Before Inventory and Analytics expansion:

1. no legacy integration blueprint or provider-form alias;
2. no retired provider-specific configuration/binding model;
3. no Kubernetes runtime metadata stored on `Cluster`;
4. no direct provider client construction outside provider modules;
5. shared UI state, navigation, status badge, pagination, and action contracts;
6. README present for each high-complexity domain;
7. architecture contract tests included in CI.

## Honest Remaining Risk

Prometheus and Alertmanager provider tables still duplicate selected identity and
runtime summary fields also present on `IntegrationInstance`. This is acceptable
for the next Inventory/Analytics batch only if writes remain synchronized through
provider lifecycle services. The next major persistence cleanup should decide
whether provider tables become connection-only records and all shared fields move
exclusively to `IntegrationInstance`.
