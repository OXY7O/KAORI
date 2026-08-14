# KAORI Analytics Resource Utilization Audit — 2026-08

## Scope

Audited Kubernetes Analytics → Resource Utilization after the Analytics Overview runtime hardening. The review covered committed-snapshot ownership, Prometheus query semantics, worker and node scope, HTMX lifecycle, loading and unavailable states, chart correctness, presentation ownership, legacy helpers, source reuse, and documentation.

## Findings and Resolution

### Hidden-tab work executed during initial page load

The full-page route resolved summary and trend materialization even though Trend Analysis was a first-activation tab. The summary materializer also queried node names, worker-node names, an all-node detail summary, a second risk assessment, and a report-oriented summary table that the initial page did not consume.

Resolution:

- the initial route resolves only `analytics.utilization.summary`;
- Trend and Node Detail own their first activation, dispatch, polling, and fragment replacement;
- summary materialization no longer queries hidden-tab selectors or node-detail payloads;
- report export retains its direct `get_summary_table()` ownership.

### Worker scope contradicted the denominator

The page described worker utilization while global CPU, memory, and pod ratios used total node capacity. Legacy `master` role labels were also not excluded consistently.

Resolution:

- CPU, memory, and pods use worker `kube_node_status_allocatable` denominators;
- worker filtering excludes both `control-plane` and `master` node roles;
- usage, top-consumer, node-list, and pod-placement expressions follow the same role boundary;
- required metric-label contracts were updated with node, role, unit, namespace, and pod identity.

### Missing capacity appeared healthy

A missing denominator could be coerced to zero and presented as Normal or Healthy.

Resolution:

- presentation checks denominator presence and a positive allocatable value;
- unavailable evidence renders `N/A`, `Unknown`, and no semantic progress fill;
- a partially available summary renders `Limited Evidence`;
- all missing evidence renders `Unknown`;
- empty risk defaults changed from `Normal` to `Unknown`.

### Derived presentation logic was duplicated in templates

Hero, overview, summary, trend, and node templates calculated labels, tones, and highest values independently. The trend template also referenced an undefined `metric_tone` value.

Resolution:

- added `app/analytics/kubernetes/utilization/presentation.py` as the canonical presentation boundary;
- moved resource rows, status/tone, posture, trend labels, node detail, and no-data semantics into Python;
- templates now consume presentation-ready values;
- removed the undefined trend tone reference.

### Trend chart could misrepresent evidence

The chart used labels from the first non-empty series, which could shift data when timestamps differed. It displayed time-only labels for long ranges and hard-clipped the scale at 100%.

Resolution:

- align all series by the timestamp union;
- preserve missing points as `null`;
- include dates for windows longer than 24 hours;
- compute a dynamic `suggestedMax` instead of enforcing `max: 100`;
- initialize only when the committed chart fragment exists.

### Fragment routes were reachable as standalone pages

Trend and Node Detail endpoints could render partial HTML through direct navigation and did not explicitly prevent fragment caching.

Resolution:

- non-HTMX access redirects to the full Resource Utilization workspace with the correct tab;
- fragment responses send `Cache-Control: no-store, max-age=0` and `Vary: HX-Request`;
- form fallback actions point to the full page while `hx-get` continues to use the fragment endpoint.

### Legacy service helpers and duplicate cluster selection

The Utilization service contained a second selected-cluster resolver and dead service/provider builders.

Resolution:

- selected cluster resolution now uses `app.analytics.kubernetes.common.clusters.resolve_selected_cluster`;
- removed the duplicate cluster resolver, dead service builders, dead endpoint helper, local duplicate coercion helper, and unused integration resolver import;
- retained `get_summary_table()` because Reports export is an active consumer.

## Canonical Ownership

| Concern | Owner |
|---|---|
| Full-page summary snapshot | `analytics.utilization.summary` |
| Historical trend snapshot | `analytics.utilization.trend` |
| Node detail snapshot | `analytics.utilization.node` |
| Resource/status presentation | `app/analytics/kubernetes/utilization/presentation.py` |
| Provider query definitions | `app/integrations/prometheus/query_profiles/kubernetes_v1.py` |
| Trend chart runtime | `app/static/js/analytics/kubernetes/utilization.js` |
| Report table payload | `app/reports/export/payloads/utilization.py` using `UtilizationService.get_summary_table()` |

## Deployment Note

The PromQL meaning changes from total node capacity to worker allocatable capacity. Existing committed snapshots can remain readable during their bounded freshness window. The next scheduled or on-demand Analytics materialization refresh replaces them using the corrected query profile. Trigger a manual Analytics materialization after deployment when immediate evidence replacement is required.

## Validation Contract

The regression contract verifies:

- summary does not resolve hidden datasets or issue hidden-tab queries;
- fragment routes require HTMX and disable caching;
- worker queries use allocatable denominators and exclude both control-plane role variants;
- missing denominator evidence is Unknown rather than Healthy zero;
- valid zero usage remains Normal evidence;
- trend no-data values remain N/A;
- chart series align by timestamp and do not clip above 100%;
- presentation labels are owned by Python;
- removed helpers and duplicate cluster selection do not return.

## Validation Result

Completed in the source-audit environment:

- 30 focused Utilization/materialization contracts passed.
- 175 of 180 Analytics static contracts passed. The five failures are unchanged baseline contracts in Capacity, Storage, Workload pagination, and Intelligence Recommendations; none reference Resource Utilization.
- Python syntax validation passed across 910 source files.
- Internal import module/symbol validation passed across 4,704 import statements.
- Jinja parsing passed for every Resource Utilization template.
- JavaScript syntax validation passed for `app/static/js/analytics/kubernetes/utilization.js`.
- Source hygiene passed across 1,915 tracked files.
- Obsolete-file audit passed after generated bytecode cleanup.
- `git diff --check` passed.
- Resource Utilization no longer has entries in the UI style debt baseline. Its resolved route-length entry was removed, and the service module ceiling was reduced from 1,275 to 1,172 lines. The Kubernetes query profile remains below its existing 1,306-line ceiling.

The application-importing Analytics and report tests could not be collected because Flask is not installed in the audit runtime. Architecture and import-cycle verifiers report the same pre-existing global cycles as the applied Analytics Overview baseline; this change does not add or expand a cycle.
