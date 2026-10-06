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

## Completed Cleanup Boundary

Revision `20260722_provider_authority` makes `IntegrationInstance` the only
shared provider identity and runtime-summary authority. Revision
`20260722_foundation_cleanup` then removes the retired `users.role` field,
converts transitional binding validation states, normalizes Prometheus binding
capability scope, and enforces canonical report storage URIs.

Provider-version compatibility remains intentional product behavior. Internal
URL redirects, Python import facades, provider-local runtime-history wrappers,
and runtime fallback branches are not part of the supported foundation.
