# Artifact Registry Alert Analytics Contract

## Purpose

Artifact Registry reuses the existing KAORI Alert Source and Analytics patterns already established by Kubernetes and Object Storage. This document records the Registry extension; it does not define a new alert engine or provider-specific lifecycle.

Authority: #952, under Registry foundation #558 and the Metrics Source / operational-health boundary in #898.

## Source Boundary

```text
Registry provider
├── metrics ──> Prometheus / Thanos ──> Metrics Source
└── alert rules ──> Alertmanager ──> Alert Source
                               │
                               ▼
                    registry_instance binding
                               │
                               ▼
                    analytics worker materialization
                               │
                               ▼
                    RegistryAnalyticsSnapshot
                               │
                               ▼
              Artifact Registry → Analytics → Alerts
```

Alertmanager is the primary alert-state authority. Metrics Source is a bounded fallback for active-alert evidence when the bound Alertmanager source is not eligible or available.

Normal Artifact Registry page rendering must not call Alertmanager, Prometheus, or Thanos directly.

## Consumer Profile

The canonical Alertmanager consumer profile is:

```text
asset_type: registry_instance
profile_key: registry-alerts-v1
```

It reuses the same required and optional Alertmanager capabilities used by the approved Kubernetes and Object Storage consumers.

A shared Alertmanager binding requires an asset selector. Existing bindings must be revalidated after this profile is introduced so validation evidence records the canonical Registry profile.

## Materialized Evidence

The Registry analytics worker normalizes the selected source into committed evidence containing, where available:

- alert name;
- severity;
- state;
- target;
- summary;
- start time;
- receiver;
- silence/inhibition state;
- fingerprint;
- labels;
- source and source key;
- fallback/source-error provenance.

Alert evidence is optional to Registry inventory, security, runtime, and governance truth. Alert-source failure must not invalidate those committed domains.

## Analytics UI

Artifact Registry Analytics follows a fast-shell pattern:

```text
GET /artifact-registry/analytics
    → Hero / shell
    → lazy Summary fragment
    → lazy active workspace fragment
```

Tabs:

```text
Growth
Capacity
Usage
Risk
Governance
Alerts
Insights
```

Only the active workspace is projected after first paint. Alerts uses committed materialization, default pagination 5, and server-backed filters for severity, state, source, and search.

## Ownership

- Alertmanager owns alert state, routing, and suppression semantics.
- Prometheus / Thanos owns metric collection and retention.
- KAORI owns binding validation, normalization, committed evidence, correlation, presentation, governance, and audit.
- Artifact Registry Analytics owns analytical projection only.
- Central Intelligence owns recommendation lifecycle, Accepted Risk, escalation, and Automation Control.
- Reliability / Incident Management owns incident lifecycle when that domain promotes alert evidence into an incident.

## Guardrails

- no Registry-local Alertmanager client or binding persistence;
- no Harbor-specific alert persistence;
- no request-time provider dependency for normal Analytics UI;
- no alert-routing, silence, or rule mutation from Artifact Registry;
- no automatic alert-to-recommendation or alert-to-incident promotion;
- no fabricated equivalence between provider-specific Registry telemetry.
