# KAORI Analytics Overview Audit — 2026-08

## Scope

The audit covers Kubernetes Analytics → Overview page composition, HTMX loading,
committed-snapshot ownership, health and recommendation semantics, drill-down
scope propagation, shared presentation primitives, source hygiene, and legacy
cleanup.

## Canonical runtime flow

```text
GET /analytics/
  -> resolve cluster and time-range scope
  -> render shell, Health Summary placeholder, and tab placeholders

HTMX health-summary request
  -> one Prometheus readiness observation
  -> read seven committed datasets with exact parameter variants
  -> build snapshot coverage and operational health
  -> build actionable summary and prioritized actions
  -> render Health Summary
  -> OOB update Hero Posture, Action Summary, and Recommendations

First domain-tab activation
  -> request only that domain presenter
  -> read only that committed snapshot
  -> replace the tab placeholder
```

Hidden domain tabs do not request data on initial page load. Action Summary and
Recommendations do not own separate composite endpoints because their payload is
already produced by Health Summary.

## Evidence rules

The expected Overview dataset set is:

1. `analytics.utilization.summary` — `cluster_id`
2. `analytics.capacity` — `cluster_id`, `time_range`
3. `analytics.storage` — `cluster_id`
4. `analytics.workload` — `cluster_id`, `time_range`
5. `analytics.top_consumers` — `cluster_id`
6. `analytics.forecast` — `cluster_id`, normalized `history_window`
7. `analytics.alerts` — `cluster_id`, `source=auto`

Freshness and availability are evaluated only against the exact expected
parameter map. A ready snapshot for another time range or source variant is not
counted as current for the selected Overview scope.

Domain adapters return `None` when committed evidence is unavailable. The
Overview schema then renders explicit Unknown/N/A states. It is prohibited to
translate missing evidence into zero utilization, zero alerts, Normal, Healthy,
or Low Risk.

Cluster Health rules:

- **Critical** when known evidence contains a critical alert, critical pressure,
  or high/critical forecast risk.
- **Warning** when known evidence contains an operational warning.
- **Limited** when no known warning exists but expected dataset coverage is
  incomplete.
- **Healthy** only when all expected datasets are current and no known warning is
  present.
- **Unknown** when no committed analytics evidence is available.

## UI and interaction decisions

- KAORI Violet shared surfaces remain canonical through
  `analytics/components/_analysis_surfaces.html`.
- All seven domain tabs load on first activation only. Tabs use the shared
  wrapping tab layout; no horizontal-scroll compatibility mode remains.
- The loading tracker counts requested sections, not hidden placeholders.
- Empty committed snapshots render the shared Snapshot Unavailable state.
- Action Summary and Recommendations distinguish Unknown, Limited, Review,
  Critical, and Normal evidence states.
- Drill-down URLs use `_scoped_link.html`; existing query strings receive `&`
  rather than a second `?`.
- Section responses use `Cache-Control: no-store, max-age=0` and
  `Vary: HX-Request`.

## Legacy cleanup

Removed:

- `app/templates/analytics/components/_overview_surfaces.html`
- `app/templates/analytics/kubernetes/overview/partials/_prometheus_status.html`
- synthetic `_empty_*_snapshot` adapters used only to convert missing evidence
  into zero-value snapshots
- `app/analytics/common/cache.py`, an unreferenced Redis/local cache from the
  pre-materialization Overview path
- legacy Overview endpoints for `prometheus-status`, `hero-posture`,
  `actionable-recommendations`, and `recommendations`

The shared Prometheus card remains canonical at
`app/templates/analytics/kubernetes/components/_prometheus_status.html` and is rendered by
Analytics Controls & Data Readiness.

## Regression contract

`tests/contracts/analytics/test_analytics_overview_runtime_integrity_contract.py`
locks:

- one composite owner;
- first-activation domain loading;
- exact snapshot parameter matching;
- Workload time-range propagation;
- `None` for unavailable domain adapters;
- Unknown/Limited semantics;
- query-string-safe drill-down links;
- legacy template removal.

## Validation result

The final source audit produced the following results:

- `27/27` focused Analytics Overview presentation and runtime contracts passed.
- `163/169` Analytics contract tests passed. The six failures are pre-existing
  contracts outside Analytics Overview: Utilization status wording, Capacity
  progress styling, Storage PV guidance styling, Workload pagination wording,
  and two Intelligence Recommendations presentation literals.
- Python syntax passed across `908` source files.
- Internal module and symbol validation passed across `4,695` import statements.
- Jinja syntax passed across `33` Analytics templates.
- JavaScript syntax passed for `analytics_overview.js` and
  `analytics_controls.js`.
- Source hygiene passed across `1,908` tracked files.
- Obsolete-file audit passed.
- The code-health verifier reports no Analytics Overview violation. Remaining
  findings are existing debt in other workspaces.

The repository archive does not contain an installed Flask runtime, so the two
application-importing Overview tests cannot be collected in the audit
container. They stop at `ModuleNotFoundError: flask`; this is an environment
limitation rather than an assertion failure.

Architecture and import-cycle verification still report the same repository
baseline cycles outside this change. No new cycle, boundary exception, or debt
baseline entry was added for Analytics Overview. Module reachability now reports
only `app/knowledge/remediation_workflow.py` and `app/users/identity.py`, both
outside this audit scope.

## Neutral visual hierarchy redesign — 2026-08-06

Analytics Overview was redesigned after light- and dark-mode review found that semantic card fills, colored icon tiles, accent bars, and colored headlines competed for attention.

Final decisions:

- panel and evidence surfaces remain neutral;
- KAORI Violet is limited to section identity, metadata, navigation, and actions;
- semantic colors are limited to compact status labels, icon glyphs, and quantitative status bars;
- Operational Health Summary uses a readable three-column grid rather than six narrow cards;
- health cards no longer use colored top accents or semantic surface fills;
- dataset-attention feedback uses a neutral strip with a compact Warning badge;
- How To Read, What To Do, Operational Reading, Recommended Action, Operational Triage, and similar guidance use one shared neutral interpretation layout;
- semantic headlines and separate accent-card variants were removed;
- Resource and Storage pressure bars continue to follow the resolved status color;
- Overview metric icons use neutral tiles; status remains visible through badges and bars;
- the same shared guidance primitives now apply across all Kubernetes Analytics pages.

This redesign changes presentation only. Evidence calculations, materialization dimensions, status thresholds, routing, and recommendation logic are unchanged.

Regression ownership:

- `tests/contracts/analytics/test_overview_semantic_visual_hierarchy_contract.py`
- `tests/contracts/analytics/test_analytics_guidance_callout_standard_contract.py`
- `tests/contracts/analytics/test_semantic_status_bar_contract.py`
- `tests/contracts/analytics/test_overview_workspace_presentation_contract.py`

## Neutral surface and typography correction — 2026-08-06

A second visual review found that removing accent bars was not sufficient because the Analytics token scope still supplied lavender supporting surfaces, purple-tinted outlines, and purple-tinted supporting text. The result looked washed out and made guidance regions compete with primary evidence.

The final correction applies the following rules:

- `kaori-analytics-page` overrides supporting surfaces with slate neutrals in light mode and charcoal neutrals in dark mode;
- Analytics supporting text uses slate rather than purple-tinted content tokens;
- guidance regions use `bg-surface-card`, not a full `bg-surface-muted` band;
- How To Read, What To Do, Recommended Action, and Review Path use the same Violet non-semantic icon treatment;
- only an actual health reading uses `role='status'` with its resolved semantic tone;
- health and pressure rows use neutral icons while status badges and quantitative bars carry semantic color;
- Dataset Attention remains neutral and uses Warning only for its glyph and compact badge;
- singular Dataset Attention grammar is corrected to `1 Dataset Needs Attention`;
- Forecast now carries `kaori-analytics-page`, removing the last cross-page token inconsistency.

This correction remains presentation-only. Analytics evidence, snapshot dimensions, thresholds, routes, and recommendation logic are unchanged.

## Cross-Analytics visual-role standardization — 2026-08-06

The neutral correction was refined after product review clarified that KAORI
color should remain expressive rather than being removed. The final contract
therefore assigns color by reusable visual role across every Analytics page:

- Brand: Bright Violet for identity, navigation, primary action, and review path;
- Insight: cyan/info for How To Read, methodology, and explanatory content;
- Evidence: slate for passive context, Namespace, workload, ownership, and scope;
- Status: semantic green, amber, red, or slate only for actual operational state.

Large evidence and guidance surfaces remain neutral for contrast. Color is
concentrated in compact icon tiles, eyebrow labels, badges, charts, and status
bars. This provides stronger use of the KAORI palette without restoring the
former visually noisy full-card tints.

The implementation is DRY:

- `role_icon_classes()` owns role icon geometry and color;
- `role_label_classes()` owns eyebrow label color;
- `resource_icon_classes()` owns resource/category mapping;
- `semantic_icon_classes()` owns status glyph presentation;
- every `interpretation_callout()` and `interpretation_content()` invocation
  explicitly declares `role=`;
- Capacity and other status-bearing bars use semantic colors, while composition,
  ranking, loading, and materialization bars remain KAORI Violet.

The system applies to Overview, Utilization, Capacity, Storage, Workload,
Forecast, Top Consumers, and Alerts & Anomalies. No domain-local compatibility
wrapper or new color-token exception was introduced.

Regression ownership:

- `tests/contracts/analytics/test_analytics_visual_role_system_contract.py`
- `tests/contracts/analytics/test_analytics_guidance_callout_standard_contract.py`
- `tests/contracts/analytics/test_semantic_status_bar_contract.py`
- `tests/contracts/analytics/test_overview_semantic_visual_hierarchy_contract.py`

## Template-scope runtime hotfix — 2026-08-06

Runtime validation after the cross-Analytics visual-role rollout found two
Jinja scope regressions in lazy-loaded Overview fragments:

- `_health_summary.html` imported the shared surface macros as
  `overview_surface` but two header icons referenced the undeclared
  `analysis_surface` alias;
- `_workload_snapshot.html` iterated with `metric` but one resource icon still
  referenced `item.label`.

Both references now use their locally declared aliases and loop variables. The
fix is presentation-only and does not change snapshot data, materialization,
status semantics, or routing.

Regression ownership is added in:

- `tests/contracts/analytics/test_overview_template_scope_contract.py`

The contract parses every Analytics Overview partial with Jinja metadata and
rejects unbound shared-surface aliases or common loop-variable names. This
covers lazy HTMX fragments that static string contracts previously did not
execute.
