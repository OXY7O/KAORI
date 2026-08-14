# Analytics Resource Utilization

Status: KAORI domain presentation and evidence standard

## Page Structure

1. Hero with selected cluster, utilization posture, highest-pressure resource, and actionable count.
2. Controls and Data Readiness with cluster, trend window, Prometheus readiness, worker scope, and committed snapshot metadata.
3. Quick Resource Utilization Overview.
4. One tabbed workspace containing Summary, Trend Analysis, Node Detail, and Recommendations.

## Scope and Denominator Contract

CPU, memory, and pod utilization use the Kubernetes worker boundary. Control-plane nodes are excluded using both canonical role labels: `control-plane` and legacy `master`.

- CPU usage is compared with worker `kube_node_status_allocatable{resource="cpu",unit="core"}`.
- Memory working set is compared with worker `kube_node_status_allocatable{resource="memory",unit="byte"}`.
- Running pods placed on workers are compared with worker `kube_node_status_allocatable{resource="pods",unit="integer"}`.
- Node filesystem evidence remains node-scoped and uses the validated `/var`, otherwise `/`, canonical filesystem identity contract.

The UI must say **allocatable**, not capacity, when describing these denominators. A missing or zero denominator is unavailable evidence. It renders `Unknown` and `N/A`; it must never be projected as zero utilization, Normal, or Healthy.

## Initial Request and Lazy Ownership

The full-page request resolves only `analytics.utilization.summary`. It must not materialize or read Trend or Node Detail data.

- Trend Analysis owns `analytics.utilization.trend` and loads on first tab activation.
- Node Detail owns `analytics.utilization.node` and loads on first tab activation.
- Hidden tabs do not query node lists, range series, node detail, or poll pending jobs.
- Direct browser navigation to a fragment endpoint redirects to the full workspace and selects the relevant tab.
- HTMX fragment responses use `Cache-Control: no-store, max-age=0` and `Vary: HX-Request`.

The summary materializer must not build report-only summary tables, node selectors, or node-detail snapshots. Those consumers own their own queries.

## Summary

Summary is not a duplicate KPI grid. It uses the shared Resource Pressure Lane to explain current percentage, absolute usage against allocatable evidence, and operational interpretation.

Presentation derivation belongs to `app/analytics/kubernetes/utilization/presentation.py`. Templates consume ready-to-render resource rows, tone, status, labels, and evidence availability. They do not calculate highest pressure, health posture, percentage status, or trend-window wording in Jinja.

## Trend Analysis

Trend Analysis loads on first activation. It contains a semantic header, peer metrics, one bright chart evidence panel, one visible CPU/Memory/Pods legend, a Resource Trend Outlook, and interpretation/action guidance.

Chart behavior belongs in `app/static/js/analytics/kubernetes/utilization.js`:

- series are aligned by the union of timestamps;
- a missing point remains `null`, not synthetic zero;
- windows longer than 24 hours include date and time in labels;
- the Y-axis uses a dynamic suggested maximum and must not clip evidence above 100%;
- the chart initializes after the committed fragment is visible and does not poll a hidden placeholder.

## Node Detail

Node Detail loads on first activation. It uses a bright scope strip, shared Resource Pressure Lanes for CPU, memory, and pods, a bright filesystem context panel, and a darker recommended-action region.

Node CPU, memory, and pod denominators use allocatable values. Missing denominator evidence renders `Unknown`/`N/A` without a semantic progress fill. Node filesystem identity must remain canonical; `instance=IP:port` is not accepted as a node fallback.

## Recommendations

Recommendations remain a paginated bright action list. A utilization recommendation deep-links using the `tab` query parameter; hash compatibility is not supported.

## Loading and Feedback

Resource Utilization does not use the Analytics Overview composite load tracker. The top filter, Trend, and Node Detail own their local indicators. Dependency failures use the canonical blocker. Source-readiness warnings use the canonical Analytics status notice and are not duplicated as custom wrappers or toast messages.
