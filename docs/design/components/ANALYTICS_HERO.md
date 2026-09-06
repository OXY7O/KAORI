# Kubernetes Analytics Hero Extension

This document extends `HERO.md` for Kubernetes Analytics and records the cross-domain Analytics metadata rule introduced by Hero Standard v1.6. It does not override shared Hero geometry, typography, state semantics, or action styling.

## Kubernetes reference composition

Kubernetes Analytics heroes use `components/page_hero.html` and contain:

1. `Kubernetes Analytics` domain eyebrow;
2. one concise page title and description;
3. exactly three metadata items in Normal operational branches;
4. reduced readiness metadata when a Blocked branch requires it;
5. one compact posture context card;
6. exactly two posture metrics;
7. one full-width `Manage Clusters` action using `server-cog` in the Normal operational branch.

Normal Analytics pages use `page_hero.context_card(...)`. Analytics Overview lazy posture uses `page_hero.context_card_body(...)` because the parent Hero owns the `<aside>` wrapper.

Domain templates provide posture labels, semantic tone, metric values/helpers, and cluster-management URL. They do not recreate posture headers, metric geometry, value scales, or action geometry.

## Analytics Readiness blocked contract

Blocked Analytics heroes remain visible and use a shared readiness context instead of presenting normal posture evidence. The right-side context uses this order:

1. eyebrow `Analytics Readiness`;
2. concise blocker title describing the missing or unavailable dependency;
3. semantic `Blocked` status badge;
4. **Active Scope** — the selected cluster/system or an explicit no-scope value;
5. **Missing Evidence** — the evidence class required to activate the workspace;
6. one concise information strip describing the next operator requirement.

Typical **Missing Evidence** values include `Cluster Context`, `System Context`, `Inventory Snapshot`, `Operational Metrics`, `Alert Evidence`, and `Analytics Snapshot`. Generic progress such as `Current Step` / `Progress` is not the primary Hero information.

Detailed remediation belongs below the Hero in the shared `Analytics Setup Path`. That surface shows Complete / Current Blocker / Pending dependency states, the missing dependency, and one permission-aware authoritative action. Domain-specific routes and permissions remain owned by the dependency blocker contract.

## Stable Kubernetes context titles

- Analytics Overview: `Analytics Status`
- Resource Utilization: `Resource Pressure`
- Capacity Analysis: `Capacity Headroom`
- Storage Analysis: `Storage Pressure`
- Workload Analysis: `Workload Governance`
- Top Consumers: `Consumer Pressure`
- Alerts & Anomalies: `Signal Readiness`
- Resource Forecast: `Forecast Outlook`

## Metadata ownership

Normal operational Analytics metadata uses three stable semantic slots. Metadata must not duplicate the two posture metrics or fabricate evidence that does not exist.

For Object Storage Analytics, the third Normal slot is an **evidence-boundary** label rather than an optional observation timestamp. `Committed Snapshot Boundary` describes the request-time data model and remains truthful even when no inventory observation timestamp is available. Observation timestamps remain evidence/detail values rather than a structural prerequisite for the Hero.

Long technical identifiers stay in evidence/detail surfaces. Hero values remain concise and unambiguous.

## Prohibited patterns

- Analytics-only Hero geometry that duplicates `page_hero`;
- domain-local blocked Hero context geometry when the shared blocked renderer applies;
- conditional Normal metadata that drops from three to two items;
- invented evidence values used only to satisfy cardinality;
- `context_posture_header(...)`;
- `context_posture_note(...)`;
- `context_bottom_notice(...)`;
- local metric typography overrides;
- more than two posture metrics;
- a second interpretation paragraph inside the context card.

Interpretation and recommended action belong below the Hero.
