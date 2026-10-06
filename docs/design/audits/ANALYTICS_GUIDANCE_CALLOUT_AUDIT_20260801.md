# Kubernetes Analytics Guidance Callout Audit — 2026-08-01

## Scope

The audit covered all Kubernetes Analytics presentation domains:

- Analytics Overview;
- Resource Utilization;
- Capacity Analysis;
- Storage Analysis;
- Workload Analysis;
- Resource Forecast;
- Top Consumers;
- Alerts & Anomalies;
- Analytics materialization failure state.

## Finding

The Overview workspace already used the reviewed icon-led guidance pattern, but full domain pages still contained page-local versions of `How To Read`, `What To Do`, `Operational Reading`, `Recommended Action`, and `Recommended Review Path`. These implementations differed in icon size, headline presence, padding, semantic color, and body typography.

## Resolution

All guidance now resolves through the canonical owner:

```text
app/templates/analytics/components/_analysis_surfaces.html
```

Canonical APIs:

```jinja
interpretation_callout(...)
interpretation_content(...)
```

The callout owner normalizes:

- semantic tone through `table_label.semantic_tone(...)`;
- icon surface and icon color;
- eyebrow label typography;
- headline scale;
- neutral body text;
- standard and compact density.

## Domain Disposition

| Domain | Standardized regions |
|---|---|
| Overview | Capacity and Storage guidance plus existing Overview guidance |
| Utilization | Current Summary, Trend, Node Detail, pressure-lane Operational Reading, thresholds |
| Capacity | Allocation, worker baseline, review path, measurement standard |
| Storage | Capacity Utilization, Storage Overview, Persistent Volume guidance |
| Workload | Overview Operational Reading, Tenant Quota actions, Workload Mapping actions |
| Forecast | Methodology reading, resource actions, combined trend guidance |
| Top Consumers | Ranking interpretation, review path, record actions |
| Alerts | Cluster Operational Reading, Incident Readiness action, anomaly review |
| Materialization | Failure remediation |

## Guardrails

- Domain templates must not render raw guidance labels in HTML.
- Section-level guidance uses `interpretation_callout(...)`.
- Existing record or side-panel wrappers use `interpretation_content(...)`.
- Expanded record actions use `compact=true`.
- Primary guidance remains visible; it is not placed behind an expandable container.
