# KAORI Operational Data Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Kubernetes and Object Storage with the approved KAORI operational-data semantics so Inventory is factual-only, Dashboard is a KAORI summary consumer, Analytics owns provider evidence and contextual recommendations, Intelligence owns durable recommendations, and Alert Intelligence owns durable AlertCases.

**Architecture:** Keep each product surface on one explicit authority boundary. Dashboard will consume read-only helpers from Intelligence and Alert Intelligence; Object Storage Analytics will stop reading central Intelligence findings for local recommendation tabs and will instead derive contextual recommendations from committed Analytics payloads. Provider alerts and anomaly signals remain Analytics evidence, while Dashboard Alert Insight stays AlertCase-backed.

**Tech Stack:** Flask, Jinja2, HTMX, Alpine.js, SQLAlchemy, Celery materialized snapshots, Ruff, Pyright, djlint, pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-kaori-operational-data-semantics-design.md`

## Global Constraints

- Inventory is factual asset truth only; it must not render Intelligence recommendations, Analytics recommendations, Alert Intelligence cases, provider-alert interpretation, forecast conclusions, or anomaly conclusions.
- Dashboard Alert Insight consumes KAORI AlertCases only; Dashboard must not count raw Prometheus/Alertmanager alerts directly.
- Dashboard Recommended Actions consumes central Intelligence Recommendations, selected domain + selected asset, actionable/active findings, priority-ranked, maximum 5.
- Analytics Overview uses Provider Alert + Anomaly summaries rather than central Recommendations.
- Analytics contextual Recommendations are current-page, current-scope, current-window, non-durable guidance derived from Analytics evidence.
- Alerts & Anomalies must distinguish Provider Alerts, Anomaly Signals, and contextual Recommendations.
- Missing evidence remains `Unknown`; it must not silently become zero, healthy, or no-alert.
- Object Storage alert provider order remains Alertmanager preferred, Metrics Source `ALERTS` fallback where defined.
- Dashboard `Alert Insight` source text is `Alert Intelligence`; metadata labels are `KAORI Alert Cases Available` and `KAORI Alert Intelligence`.
- Notification Deck progress tracks use the same full-width `h-1.5` track; proportional fill must continue to reflect actual progress percentage.
- No static-quality, architecture, UI-style, code-health, or debt baseline may be increased to make this implementation pass.
- All cross-surface reads remain RBAC-scoped and read-only.

---

## File Map

### New shared/semantic ownership

- Create `app/intelligence/dashboard_recommendations.py` — Dashboard-only read interface for central Intelligence findings; no Analytics logic.
- Modify `app/intelligence/alert_intelligence/dashboard_cases.py` — retain AlertCase query ownership and expose canonical Dashboard Alert Insight labels/helpers only if needed by both Dashboard families.
- Replace `app/storage/object_storage/analytics/recommendations.py` — Object Storage Analytics-local contextual recommendation builders; no import of `app.intelligence.service` or `get_active_recommendation_findings`.
- Create `app/storage/object_storage/analytics/overview_alerts.py` — build Overview Alerts summary from committed provider-alert stream + metric-derived anomaly evidence without overwriting Overview metrics.

### Dashboard consumers

- Modify `app/kubernetes/dashboard/sections/recommendations.py`
- Modify `app/kubernetes/dashboard/service.py`
- Modify `app/templates/kubernetes/dashboard/partials/_alerts_summary.html`
- Modify `app/templates/kubernetes/dashboard/partials/_recommended_actions.html`
- Modify `app/storage/object_storage/dashboard/service.py`
- Modify `app/storage/object_storage/dashboard/presentation.py`
- Modify `app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html`
- Modify `app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html`

### Object Storage Analytics

- Modify `app/storage/object_storage/analytics/routes.py`
- Modify `app/storage/object_storage/analytics/service.py`
- Modify `app/templates/storage/object_storage/analytics/partials/_overview_workspace.html`
- Create `app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_performance_workspace.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html`
- Replace `app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_hero_posture.html` if central-finding wording remains.

### Regression repairs and presentation contracts

- Modify `app/templates/components/progress_bar.html`
- Modify `app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html`
- Modify `app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html`
- Modify `app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html`
- Modify `app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html`
- Modify `app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html`
- Modify `app/templates/kubernetes/analytics/alerts/partials/_alerts_table.html`
- Modify `app/templates/kubernetes/analytics/alerts/partials/_anomalies_table.html`
- Modify `app/templates/storage/object_storage/analytics/partials/_bucket_table.html`

### Tests/verifiers/docs

- Create `tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py`
- Modify `tests/contracts/dashboards/test_dashboard_alert_source_unification_20260824_contract.py`
- Modify `tests/contracts/dashboards/test_alert_summary_source_layout_20260825_contract.py`
- Create `tests/contracts/dashboards/test_dashboard_recommended_actions_semantics_20260825_contract.py`
- Modify `tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py`
- Create `tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py`
- Modify `tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py`
- Create `tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py`
- Add runtime coverage under `tests/kubernetes/dashboard/` and `tests/storage/object_storage/analytics/` where existing fixtures permit.
- Modify `scripts/verify_object_storage_analytics.py`
- Create `scripts/verify_operational_data_semantics.py`
- Modify `docs/architecture/README.md`
- Modify `docs/architecture/quality-gates.md`

---

### Task 1: Lock Cross-Surface Semantic Contracts

**Files:**
- Create: `tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py`
- Create: `scripts/verify_operational_data_semantics.py`
- Modify: `docs/architecture/README.md`
- Modify: `docs/architecture/quality-gates.md`

**Interfaces:**
- Consumes: the approved semantic spec only.
- Produces: one canonical verifier command, `python scripts/verify_operational_data_semantics.py`, that later tasks must keep green.

- [ ] **Step 0: Mark the implementation base commit**

```bash
git tag kaori-operational-semantics-base-20260825 HEAD
```

This tag is used only to build the final changed-files-only delivery archive.

- [ ] **Step 1: Write the failing architecture contract**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_dashboard_and_analytics_use_distinct_recommendation_authorities() -> None:
    os_analytics = read('app/storage/object_storage/analytics/recommendations.py')
    os_dashboard = read('app/storage/object_storage/dashboard/service.py')

    assert 'get_active_recommendation_findings' not in os_analytics
    assert 'get_dashboard_recommendation_findings' in os_dashboard


def test_object_storage_overview_uses_alerts_not_recommendations() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    assert "('alerts', 'Alerts', 'bell-ring')" in overview
    assert "('recommendations', 'Recommendations'" not in overview


def test_dashboard_alert_insight_uses_canonical_labels() -> None:
    for path in (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
    ):
        source = read(path)
        assert '>Alert Intelligence<' in source or "'Alert Intelligence'" in source
        assert 'KAORI Alert Cases Available' in source
        assert 'KAORI Alert Intelligence' in source
        assert 'Top 3 Cases' not in source
```

- [ ] **Step 2: Run the contract and verify RED**

Run:
```bash
pytest -q tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py
```

Expected: FAIL because Object Storage Analytics still imports central Intelligence recommendations, Overview still has a Recommendations tab, and Dashboard presentation is not fully canonical.

- [ ] **Step 3: Add the verifier shell without weakening assertions**

Create `scripts/verify_operational_data_semantics.py` as a small source-contract verifier that checks the same boundaries using `Path.read_text()`. It must exit non-zero with a precise message if any authority boundary regresses.

- [ ] **Step 4: Register the verifier in architecture documentation**

Add one entry to `docs/architecture/README.md` and `docs/architecture/quality-gates.md`:

```text
python scripts/verify_operational_data_semantics.py
```

Describe it as the guard for Inventory/Dashboard/Analytics/Intelligence/Alert Intelligence source ownership.

- [ ] **Step 5: Commit the failing semantic guard**

```bash
git add \
  tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py \
  scripts/verify_operational_data_semantics.py \
  docs/architecture/README.md \
  docs/architecture/quality-gates.md
git commit -m "test: lock operational data semantics"
```

---

### Task 2: Normalize Dashboard Alert Insight and Recommended Actions

**Files:**
- Create: `app/intelligence/dashboard_recommendations.py`
- Modify: `app/intelligence/alert_intelligence/dashboard_cases.py`
- Modify: `app/kubernetes/dashboard/sections/recommendations.py`
- Modify: `app/kubernetes/dashboard/service.py`
- Modify: `app/storage/object_storage/dashboard/service.py`
- Modify: `app/storage/object_storage/dashboard/presentation.py`
- Modify: `app/templates/kubernetes/dashboard/partials/_alerts_summary.html`
- Modify: `app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html`
- Modify: `app/templates/kubernetes/dashboard/partials/_recommended_actions.html`
- Modify: `app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html`
- Test: `tests/contracts/dashboards/test_dashboard_alert_source_unification_20260824_contract.py`
- Test: `tests/contracts/dashboards/test_alert_summary_source_layout_20260825_contract.py`
- Create: `tests/contracts/dashboards/test_dashboard_recommended_actions_semantics_20260825_contract.py`

**Interfaces:**
- Produces:

```python
MAX_DASHBOARD_RECOMMENDATIONS = 5


def get_dashboard_recommendation_findings(
    *,
    domain: str,
    asset_key: str | None,
    limit: int = MAX_DASHBOARD_RECOMMENDATIONS,
) -> list[dict[str, Any]]: ...
```

- Consumes: `app.intelligence.service.get_active_recommendation_findings` only inside the new Intelligence-owned helper.
- Dashboard services must not construct durable Recommended Actions from local capacity/forecast/top-consumer heuristics.

- [ ] **Step 1: Write a failing Dashboard Recommended Actions contract**

```python
def test_both_dashboards_use_central_intelligence_top_five() -> None:
    helper = read('app/intelligence/dashboard_recommendations.py')
    k8s = read('app/kubernetes/dashboard/sections/recommendations.py')
    object_storage = read('app/storage/object_storage/dashboard/service.py')

    assert 'MAX_DASHBOARD_RECOMMENDATIONS = 5' in helper
    assert "domain='kubernetes'" in k8s
    assert "domain='object_storage'" in object_storage
    assert 'build_recommended_actions(' not in object_storage
```

- [ ] **Step 2: Run RED**

```bash
pytest -q \
  tests/contracts/dashboards/test_dashboard_recommended_actions_semantics_20260825_contract.py \
  tests/contracts/dashboards/test_dashboard_alert_source_unification_20260824_contract.py \
  tests/contracts/dashboards/test_alert_summary_source_layout_20260825_contract.py
```

Expected: FAIL on Object Storage local action construction and inconsistent Alert Insight metadata.

- [ ] **Step 3: Implement the Intelligence-owned Dashboard recommendation reader**

Create `app/intelligence/dashboard_recommendations.py`:

```python
from __future__ import annotations

from typing import Any

from app.intelligence.service import get_active_recommendation_findings

MAX_DASHBOARD_RECOMMENDATIONS = 5


def get_dashboard_recommendation_findings(
    *,
    domain: str,
    asset_key: str | None,
    limit: int = MAX_DASHBOARD_RECOMMENDATIONS,
) -> list[dict[str, Any]]:
    normalized_asset = str(asset_key or '').strip() or None
    return get_active_recommendation_findings(
        domain=domain,
        asset_key=normalized_asset,
        limit=min(max(limit, 0), MAX_DASHBOARD_RECOMMENDATIONS),
    )
```

Keep ranking authority inside `get_active_recommendation_findings`; Dashboard only caps consumption.

- [ ] **Step 4: Adapt Kubernetes Dashboard to the new helper**

Replace `build_dashboard_recommendations()` usage in `app/kubernetes/dashboard/sections/recommendations.py` with `get_dashboard_recommendation_findings(domain='kubernetes', asset_key=selected_cluster_id)` and preserve the existing `RecommendationItem` adapter.

- [ ] **Step 5: Replace Object Storage local Recommended Actions**

In `app/storage/object_storage/dashboard/service.py`, remove the call that passes `alerts`, `capacity`, `forecast`, and `top_consumers` into `build_recommended_actions()`. Add a focused adapter that maps central findings to the same card contract used by Kubernetes:

```python
def _recommended_actions(system: ObjectStorageSystem | None) -> list[dict[str, str]]:
    findings = get_dashboard_recommendation_findings(
        domain='object_storage',
        asset_key=str(system.id) if system is not None else None,
    )
    return [
        {
            'title': str(item.get('title') or 'Review recommendation'),
            'description': str(item.get('recommended_action') or item.get('summary') or ''),
            'category': str(item.get('category_label') or item.get('category') or 'Operations'),
            'severity': str(item.get('severity') or 'info'),
            'priority': str(item.get('priority') or 'P3'),
            'source': str(item.get('signal_source_label') or item.get('signal_source') or 'Intelligence'),
            'rule_key': str(item.get('rule_key') or ''),
        }
        for item in findings
    ]
```

Delete `build_recommended_actions()` and `_action()` from `app/storage/object_storage/dashboard/presentation.py` once no consumer remains.

- [ ] **Step 6: Canonicalize Alert Insight presentation**

In both Dashboard templates:

- `Source` value must be literal `Alert Intelligence`;
- do not use `truncate` for source;
- include `KAORI Alert Cases Available` status label when case evidence is available;
- always include metadata label `KAORI Alert Intelligence`;
- remove `Top N Cases` metadata variation from Kubernetes;
- keep the actual case preview list above the Alert Insight summary unchanged.

Target shape:

```jinja
<dt class="text-content-muted">Source</dt>
<dd class="mt-1 whitespace-normal text-sm font-semibold leading-5 text-content-primary">Alert Intelligence</dd>
...
{{ table_label.status_indicator_label('KAORI Alert Cases Available', 'normal') }}
{{ table_label.metadata_label('KAORI Alert Intelligence', icon='brain-circuit') }}
```

- [ ] **Step 7: Align Recommended Actions card copy**

Use the same section description on both dashboards:

```text
Top active findings from the Intelligence recommendation catalog.
```

Both cards must link to canonical Intelligence recommendation detail, not directly to Analytics pages synthesized from category.

- [ ] **Step 8: Run Dashboard contracts**

```bash
pytest -q tests/contracts/dashboards
python scripts/verify_operational_dashboard_standard.py
python scripts/verify_operational_data_semantics.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add \
  app/intelligence/dashboard_recommendations.py \
  app/intelligence/alert_intelligence/dashboard_cases.py \
  app/kubernetes/dashboard/sections/recommendations.py \
  app/kubernetes/dashboard/service.py \
  app/storage/object_storage/dashboard/service.py \
  app/storage/object_storage/dashboard/presentation.py \
  app/templates/kubernetes/dashboard/partials/_alerts_summary.html \
  app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html \
  app/templates/kubernetes/dashboard/partials/_recommended_actions.html \
  app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html \
  tests/contracts/dashboards
git commit -m "refactor: normalize dashboard intelligence consumers"
```

---

### Task 3: Replace Object Storage Overview Recommendations with Alerts

**Files:**
- Create: `app/storage/object_storage/analytics/overview_alerts.py`
- Modify: `app/storage/object_storage/analytics/service.py`
- Modify: `app/templates/storage/object_storage/analytics/partials/_overview_workspace.html`
- Create: `app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html`
- Modify: `tests/contracts/analytics/test_object_storage_analytics_contract.py`
- Create: `tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py`

**Interfaces:**
- Produces:

```python
def build_overview_alert_summary(
    *,
    payload: dict[str, Any],
    selected_source: str,
) -> dict[str, Any]: ...
```

Return keys:

```python
{
    'source': {...},
    'posture': {...},
    'provider_alert_count': int,
    'critical_count': int,
    'warning_count': int,
    'anomaly_count': int,
    'anomaly_tone': str,
    'evidence_available': bool,
    'degraded': bool,
}
```

- [ ] **Step 1: Write failing Overview semantics tests**

```python
def test_object_storage_overview_has_alerts_tab_and_no_recommendations_tab() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    assert "('alerts', 'Alerts', 'bell-ring')" in overview
    assert 'object-storage-overview-content-panel-alerts' in overview
    assert 'object-storage-overview-content-panel-recommendations' not in overview
```

Add a source contract that `overview_alerts.py` imports `resolve_materialized_alert_stream`, `build_alert_posture`, and reads `page_metrics['alerts']`, but does not import Alert Intelligence or central Intelligence recommendations.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py
```

- [ ] **Step 3: Implement `build_overview_alert_summary`**

Use the committed snapshot only:

```python
streams = payload.get('alert_streams') if isinstance(payload.get('alert_streams'), dict) else {}
stream = resolve_materialized_alert_stream(streams, selected_source=selected_source)
posture = build_alert_posture(stream)
alerts_metrics = (payload.get('page_metrics') or {}).get('alerts') or {}
signals = list(alerts_metrics.get('signals') or [])
```

Count actionable anomaly signals by tone/status without manufacturing AlertCases.

- [ ] **Step 4: Attach Overview Alerts without replacing Overview metrics**

In `get_object_storage_analytics_context()`, after the committed snapshot is attached and before the normal page-metrics return path:

```python
if page_key == 'overview':
    context['overview_alerts'] = build_overview_alert_summary(
        payload=payload,
        selected_source=context['selected_alert_source'],
    )
```

Do not call `_apply_alert_snapshot_context()` for Overview because that function intentionally switches `context['metrics']` to the Alerts dataset.

- [ ] **Step 5: Build the Overview Alerts partial**

The partial must show:

- Provider Alerts total and highest provider severity;
- active provider source label (`Alertmanager` or `Metrics Source`);
- anomaly-signal count separately;
- explicit unavailable/degraded state;
- `View Alerts & Anomalies` link to `analytics.object_storage_alerts` preserving `system_id`, `time_range`, and selected alert source.

Do not show Intelligence Recommendations or AlertCase counts in this Analytics tab.

- [ ] **Step 6: Run targeted tests**

```bash
pytest -q \
  tests/contracts/analytics/test_object_storage_analytics_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py
python scripts/verify_object_storage_analytics.py
python scripts/verify_operational_data_semantics.py
```

- [ ] **Step 7: Commit**

```bash
git add \
  app/storage/object_storage/analytics/overview_alerts.py \
  app/storage/object_storage/analytics/service.py \
  app/templates/storage/object_storage/analytics/partials/_overview_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html \
  tests/contracts/analytics/test_object_storage_analytics_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py
git commit -m "feat: add object storage analytics overview alerts"
```

---

### Task 4: Rebuild Object Storage Contextual Analytics Recommendations

**Files:**
- Replace: `app/storage/object_storage/analytics/recommendations.py`
- Modify: `app/storage/object_storage/analytics/service.py`
- Replace: `app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_performance_workspace.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html`
- Modify: `tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py`
- Test: `tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py`

**Interfaces:**
- Produces a non-durable card contract:

```python
class AnalyticsRecommendation(TypedDict):
    priority: str
    tone: str
    title: str
    description: str
    source_label: str
    icon: str
    target_tab: str
    is_actionable: bool
```

- Produces:

```python
def build_capacity_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]: ...
def build_performance_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]: ...
def build_forecast_recommendations(
    metrics: dict[str, Any],
    materialization: dict[str, Any],
) -> list[AnalyticsRecommendation]: ...
def build_top_consumer_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]: ...
def build_alert_recommendations(
    *,
    alert_posture: dict[str, Any],
    metrics: dict[str, Any],
) -> list[AnalyticsRecommendation]: ...
```

- Must not import `app.intelligence.service`, `get_active_recommendation_findings`, `decorate_recommendation_findings`, or AlertCase models.

- [ ] **Step 1: Rewrite recommendation contracts to RED**

Tests must assert:

```python
assert 'get_active_recommendation_findings' not in source
assert 'decorate_recommendation_findings' not in source
for builder in (
    'build_capacity_recommendations',
    'build_performance_recommendations',
    'build_forecast_recommendations',
    'build_top_consumer_recommendations',
    'build_alert_recommendations',
):
    assert f'def {builder}(' in source
```

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py
```

Expected: FAIL because current Object Storage recommendations are central Intelligence findings filtered by page key.

- [ ] **Step 3: Implement a small recommendation constructor**

Inside `recommendations.py`:

```python
def _recommendation(
    *,
    priority: str,
    tone: str,
    title: str,
    description: str,
    source_label: str,
    icon: str,
    target_tab: str,
    is_actionable: bool = True,
) -> AnalyticsRecommendation:
    return {
        'priority': priority,
        'tone': tone,
        'title': title,
        'description': description,
        'source_label': source_label,
        'icon': icon,
        'target_tab': target_tab,
        'is_actionable': is_actionable,
    }
```

Keep thresholds aligned with existing Object Storage posture functions; do not invent a second threshold system. Reuse state already committed in `metrics`, such as utilization tone/posture, request error posture, waiting/offline evidence, forecast ETA/state, bucket concentration, and metric-risk signals.

- [ ] **Step 4: Implement Capacity & Usage recommendations**

Derive actions from current page evidence only:

- capacity utilization/headroom warning or critical posture;
- bucket quota pressure;
- positive usage growth with constrained headroom;
- missing required capacity evidence returns context/unknown guidance, not healthy.

Every card uses `source_label` values such as `Capacity & Usage`, `Bucket Quota`, or `Usage Trend`.

- [ ] **Step 5: Implement Performance recommendations**

Use:

- request error ratio/posture;
- waiting requests;
- offline storage nodes;
- throughput direction only as context, never standalone health;
- inflight requests only when a provider-specific boundary exists; otherwise context-only.

- [ ] **Step 6: Implement Forecast recommendations**

Use:

- forecast materialization usability;
- history coverage/quality;
- growth direction;
- projected 30-day utilization;
- days-to-capacity / quota ETA where available.

A missing/stale forecast must produce Unknown/evidence-gap guidance rather than a normal recommendation.

- [ ] **Step 7: Implement Top Consumers recommendations**

Use:

- leading-bucket concentration;
- contribution/share;
- quota pressure;
- request/error evidence gaps for ranked consumers.

Do not compare heterogeneous units directly.

- [ ] **Step 8: Attach page-local recommendations in service context**

Replace the early `context.update(build_recommendation_context(system, page_key=page_key))` call with recommendation attachment after the correct page metrics are loaded. For example:

```python
if page_key == 'capacity':
    context['recommendation_cards'] = build_capacity_recommendations(context['metrics'])
elif page_key == 'performance':
    context['recommendation_cards'] = build_performance_recommendations(context['metrics'])
...
context['recommendation_count'] = sum(1 for item in context['recommendation_cards'] if item['is_actionable'])
```

This ordering is critical: contextual recommendations must depend on the committed page evidence, not only on the selected system identity.

- [ ] **Step 9: Replace the recommendation template with Analytics semantics**

Remove:

- `resource_detail_modal`;
- Intelligence rule keys;
- `Central Intelligence findings` copy;
- Alert-handling state;
- links to `intelligence.recommendation_details`.

Render cards like Kubernetes Analytics:

```jinja
{{ table_label.status_label('Priority: ' ~ item.priority, tone=item.tone, size='compact') }}
{{ table_label.metadata_label('Derived From: ' ~ item.source_label, 'database-zap', size='compact') }}
<h4>{{ item.title }}</h4>
<p>{{ item.description }}</p>
```

The Review action returns the operator to a relevant tab in the same Object Storage Analytics page, preserving `system_id` and `time_range`.

- [ ] **Step 10: Run recommendation tests**

```bash
pytest -q \
  tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py \
  tests/storage/object_storage/analytics/test_analysis.py
```

Expected in the devcontainer: PASS, including runtime evidence-change tests.

- [ ] **Step 11: Commit**

```bash
git add \
  app/storage/object_storage/analytics/recommendations.py \
  app/storage/object_storage/analytics/service.py \
  app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_performance_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html \
  tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py
git commit -m "refactor: derive object storage analytics recommendations locally"
```

---

### Task 5: Separate Provider Alerts, Anomaly Signals, and Alert Recommendations

**Files:**
- Modify: `app/storage/object_storage/analytics/service.py`
- Modify: `app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_alerts_summary.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_alert_records.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_alerts_signal_records.html`
- Modify: `tests/contracts/analytics/test_object_storage_analytics_contract.py`
- Modify: `tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py`

**Interfaces:**
- Provider Alerts continue to come from `resolve_materialized_alert_stream()`.
- Anomaly Signals continue to come from `metric_risk_signals()` committed in the Alerts page metrics.
- `build_alert_recommendations()` from Task 4 consumes those two evidence families but produces non-durable guidance only.

- [ ] **Step 1: Write failing presentation assertions**

Require the Alerts workspace to contain the explicit labels:

```text
Provider Alerts
Anomaly Signals
Recommendations
```

and reject ambiguous heading-only use of `Alert Records` where the source family is not clear.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py
```

- [ ] **Step 3: Rename workspace tabs and supporting copy**

Use:

```python
[
    ('overview', 'Alert Overview', 'radar'),
    ('records', 'Provider Alerts', 'bell-ring'),
    ('signals', 'Anomaly Signals', 'list-tree'),
    ('recommendations', 'Recommendations', 'list-checks'),
    ('evidence', 'Evidence', 'list-checks'),
]
```

The Overview copy must state that Alertmanager is preferred and Metrics Source fallback is narrower lifecycle evidence.

- [ ] **Step 4: Ensure missing provider evidence remains Unknown**

When neither provider alert stream nor operational Metrics Source evidence is available, render unavailable/unknown state. Do not show `0 Provider Alerts` as proof of health.

- [ ] **Step 5: Run targeted Alert tests**

```bash
pytest -q \
  tests/contracts/analytics/test_object_storage_analytics_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py \
  tests/contracts/analytics/test_alerts_anomalies_workspace_standard_contract.py
python scripts/verify_object_storage_analytics.py
```

- [ ] **Step 6: Commit**

```bash
git add \
  app/storage/object_storage/analytics/service.py \
  app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html \
  app/templates/storage/object_storage/analytics/partials/_alerts_summary.html \
  app/templates/storage/object_storage/analytics/partials/_alert_records.html \
  app/templates/storage/object_storage/analytics/partials/_alerts_signal_records.html \
  tests/contracts/analytics
git commit -m "refactor: separate object storage alert evidence families"
```

---

### Task 6: Repair Current Analytics/UI Regressions and Pyright Redirect

**Files:**
- Modify: `app/storage/object_storage/analytics/routes.py`
- Modify: `app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html`
- Modify: `app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html`
- Modify: `app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html`
- Modify: `app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html`
- Modify: `app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html`
- Modify: `app/templates/kubernetes/analytics/alerts/partials/_alerts_table.html`
- Modify: `app/templates/kubernetes/analytics/alerts/partials/_anomalies_table.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_bucket_table.html`
- Modify: `tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py`

**Interfaces:**
- No new domain behavior; restores previously approved KAORI UI contracts.

- [ ] **Step 1: Reproduce the four failing contracts from the user run**

```bash
pytest -q tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py
```

Expected: 4 FAIL on stacked loading, embedded alert/anomaly shell, HTMX bucket filters, and top-consumer wording.

- [ ] **Step 2: Restore stacked loading geometry**

For PVC, PV, Workload Resource Mapping, and Consumer Records headers, ensure:

```html
data-kaori-record-header="stacked-loading"
```

and use a non-horizontal outer header so `loading_bar.render(...)` occupies a full-width row below title/actions.

- [ ] **Step 3: Restore embedded Alerts/Anomalies record shells**

Use:

```jinja
{% call evidence_list.shell('Active Alert Records', embedded=true) %}
{% call evidence_list.shell('Anomaly Candidates', embedded=true) %}
```

so the workspace owns the outer border/radius/shadow.

- [ ] **Step 4: Restore HTMX auto-filter for Object Storage bucket tables**

The form must use:

```html
hx-trigger="keyup[event.target.name === 'bucket_q'] changed delay:450ms, search[event.target.name === 'bucket_q']"
```

and must not render `Apply Filter`. Preserve Clear Filter and the canonical loading indicator.

- [ ] **Step 5: Restore Top Consumer wording**

Use the already-approved copy exactly:

```text
Compare consumption, scope contribution, denominator context, and priority without comparing unlike resource units.
```

and:

```text
Consumption ranks the largest users; Contribution shows each consumer’s share of the selected scope; Pressure compares observed usage with available capacity.
```

- [ ] **Step 6: Make the legacy Object Storage recommendations route type-safe and semantically correct**

Do not pass `**dict[str, str]` directly to Flask `url_for()`, because Pyright treats reserved keyword parameters such as `_external` specially.

Use explicit canonical redirect semantics:

```python
from urllib.parse import urlencode


@permission_required('object_storage_analytics.view')
def object_storage_recommendations() -> ResponseReturnValue:
    params = {'domain': 'object_storage'}
    system_id = str(request.args.get('system_id') or '').strip()
    if system_id:
        params['asset'] = system_id
    target = url_for('intelligence.recommendations')
    return redirect(f'{target}?{urlencode(params)}')
```

This old route now points to the correct durable-recommendation owner instead of pretending a generic Analytics Recommendations page still exists.

- [ ] **Step 7: Format the contract source exactly as Ruff expects**

Run write-mode:

```bash
python -m ruff format tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py
```

Do not hand-maintain quote wrapping against Ruff output.

- [ ] **Step 8: Verify GREEN**

```bash
pytest -q tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py
python -m pyright app/storage/object_storage/analytics/routes.py
```

Expected: PASS / `0 errors`.

- [ ] **Step 9: Commit**

```bash
git add \
  app/storage/object_storage/analytics/routes.py \
  app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html \
  app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html \
  app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html \
  app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html \
  app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html \
  app/templates/kubernetes/analytics/alerts/partials/_alerts_table.html \
  app/templates/kubernetes/analytics/alerts/partials/_anomalies_table.html \
  app/templates/storage/object_storage/analytics/partials/_bucket_table.html \
  tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py
git commit -m "fix: restore analytics table and filter standards"
```

---

### Task 7: Lock Notification Deck Progress Geometry

**Files:**
- Modify only if required: `app/templates/components/progress_bar.html`
- Create: `tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py`

**Interfaces:**
- `notification_track_classes()` must continue to return a full-width `h-1.5` track.
- `notification_progress(value)` must continue to use the real value for proportional fill.

- [ ] **Step 1: Write the geometry contract**

```python
def test_notification_progress_uses_one_track_geometry_and_real_percentage_fill() -> None:
    source = read('app/templates/components/progress_bar.html')
    assert 'h-1.5 w-full overflow-hidden rounded-full' in source
    assert 'notification_progress(value' in source
    assert 'bar(value' in source
    assert 'w-full' in source
```

Also assert the compact job item wraps `progress_bar.job_progress(...)` in `w-full`.

- [ ] **Step 2: Run test**

```bash
pytest -q tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py
```

If it already passes, do not change production code. This task is allowed to be contract-only because the screenshot difference is expected proportional fill, not a component defect.

- [ ] **Step 3: Run Notification verifiers**

```bash
python scripts/verify_notification_activity_center.py
python scripts/verify_notification_center_final_lock.py
python scripts/verify_notification_surface_style.py
```

- [ ] **Step 4: Commit**

```bash
git add tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py app/templates/components/progress_bar.html
git commit -m "test: lock notification progress geometry"
```

If `progress_bar.html` is unchanged, omit it from `git add`.

---

### Task 8: Add Runtime Evidence-Change Tests and Inventory Guardrails

**Files:**
- Create or modify: `tests/storage/object_storage/analytics/test_analysis.py`
- Modify: `tests/kubernetes/dashboard/test_kubernetes_dashboard_characterization.py`
- Create: `tests/contracts/inventory/test_inventory_operational_semantics_20260825_contract.py`

**Interfaces:**
- No production interfaces added.
- Runtime tests prove behavior changes when evidence changes rather than only source-text ownership.

- [ ] **Step 1: Add Object Storage contextual recommendation runtime tests**

Create representative payloads and assert:

```python
def test_capacity_recommendations_change_with_headroom_pressure() -> None:
    normal = build_capacity_recommendations({'utilization': 40.0, ...})
    pressured = build_capacity_recommendations({'utilization': 91.0, ...})
    assert pressured != normal
    assert any(item['priority'] in {'P1', 'P2'} for item in pressured)
```

Add equivalent focused tests for performance error pressure and forecast evidence gaps.

- [ ] **Step 2: Add Dashboard max-five runtime/characterization assertion**

Using the existing dashboard test fixtures, assert Dashboard Recommended Actions never exceed five and remain central-finding-backed.

- [ ] **Step 3: Add Inventory factual-only source contracts**

Scan Kubernetes and Object Storage Inventory template roots for prohibited interpretation tokens such as imports/links to Intelligence Recommendations or Alert Intelligence. Scope the test to ownership primitives, not innocent explanatory words such as `warning` or `status`.

Example:

```python
assert 'intelligence.recommendation_details' not in inventory_templates
assert 'alert_intelligence.index' not in inventory_templates
assert 'get_active_recommendation_findings' not in inventory_services
```

- [ ] **Step 4: Run runtime + contract tests**

```bash
pytest -q \
  tests/storage/object_storage/analytics \
  tests/kubernetes/dashboard \
  tests/contracts/inventory/test_inventory_operational_semantics_20260825_contract.py
```

Expected in devcontainer: PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  tests/storage/object_storage/analytics \
  tests/kubernetes/dashboard \
  tests/contracts/inventory/test_inventory_operational_semantics_20260825_contract.py
git commit -m "test: prove operational semantics at runtime"
```

---

### Task 9: Full Standardization, Static Quality, and Release Gate

**Files:**
- Modify only files reported by formatters/verifiers from Tasks 1–8.
- Do not change debt baselines unless the implementation genuinely removes debt and baseline integrity explicitly requires lowering an exact snapshot.

**Interfaces:**
- Final deliverable is a release-candidate working tree with all approved semantic contracts active.

- [ ] **Step 1: Format changed Python**

```bash
python -m ruff format \
  app/intelligence/dashboard_recommendations.py \
  app/intelligence/alert_intelligence/dashboard_cases.py \
  app/kubernetes/dashboard \
  app/storage/object_storage/dashboard \
  app/storage/object_storage/analytics \
  scripts/verify_operational_data_semantics.py \
  scripts/verify_object_storage_analytics.py \
  tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py \
  tests/contracts/dashboards \
  tests/contracts/analytics \
  tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py
```

- [ ] **Step 2: Autofix changed Python lint only**

```bash
python -m ruff check \
  app/intelligence/dashboard_recommendations.py \
  app/intelligence/alert_intelligence/dashboard_cases.py \
  app/kubernetes/dashboard \
  app/storage/object_storage/dashboard \
  app/storage/object_storage/analytics \
  scripts/verify_operational_data_semantics.py \
  scripts/verify_object_storage_analytics.py \
  tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py \
  tests/contracts/dashboards \
  tests/contracts/analytics \
  tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py \
  --fix
```

- [ ] **Step 3: Format changed Jinja templates**

```bash
python -m djlint \
  app/templates/kubernetes/dashboard \
  app/templates/storage/object_storage/dashboard \
  app/templates/storage/object_storage/analytics \
  app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html \
  app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html \
  app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html \
  app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html \
  app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html \
  app/templates/kubernetes/analytics/alerts/partials/_alerts_table.html \
  app/templates/kubernetes/analytics/alerts/partials/_anomalies_table.html \
  app/templates/components/progress_bar.html \
  --reformat
```

- [ ] **Step 4: Run focused semantic/regression suite**

```bash
pytest -q \
  tests/contracts/architecture/test_operational_data_semantics_20260825_contract.py \
  tests/contracts/dashboards \
  tests/contracts/analytics/test_object_storage_analytics_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_recommendations_20260824_contract.py \
  tests/contracts/analytics/test_object_storage_analytics_semantics_20260825_contract.py \
  tests/contracts/analytics/test_record_table_loading_and_htmx_standard_20260824_contract.py \
  tests/contracts/platform_operations/notifications/test_notification_progress_geometry_20260825_contract.py
```

- [ ] **Step 5: Run canonical verifiers**

```bash
python scripts/verify_operational_data_semantics.py
python scripts/verify_operational_dashboard_standard.py
python scripts/verify_object_storage_analytics.py
python scripts/verify_analytics_final_lock.py
python scripts/verify_notification_activity_center.py
python scripts/verify_notification_center_final_lock.py
python scripts/verify_notification_surface_style.py
python scripts/verify_ui_style.py
python scripts/verify_ui_reuse.py
python scripts/verify_architecture_boundaries.py
python scripts/verify_automation_control.py
python scripts/verify_code_health.py
python scripts/verify_code_health_baseline_integrity.py
```

- [ ] **Step 6: Run full static/type gates**

```bash
python -m ruff format --check .
python -m ruff check .
python -m pyright --project pyrightconfig.json
```

Expected: zero Ruff and Pyright errors.

- [ ] **Step 7: Run full contract and runtime suites**

```bash
pytest -q tests/contracts
pytest -q tests/storage/object_storage/analytics tests/kubernetes/dashboard
```

- [ ] **Step 8: Run final release**

```bash
python scripts/verify_final_release.py --all
```

Expected: PASS in the real KAORI devcontainer. Do not interpret a missing local dependency in another environment as a passing release gate.

- [ ] **Step 9: Review staged diff and commit final integration**

```bash
git diff --check
git status --short
git diff --stat
```

If all Task commits exist and no formatter-only residue remains, create the final integration commit only if necessary:

```bash
git add -A
git diff --cached --check
git commit -m "refactor: enforce KAORI operational data semantics"
```

- [ ] **Step 10: Build changed-files-only delivery ZIP**

From the implementation branch, derive files from Git rather than a hand-maintained list:

```bash
git diff --name-only kaori-operational-semantics-base-20260825..HEAD > /tmp/kaori_semantics_changed_files.txt
zip -@ KAORI_operational_data_semantics_20260825.zip < /tmp/kaori_semantics_changed_files.txt
unzip -t KAORI_operational_data_semantics_20260825.zip
sha256sum KAORI_operational_data_semantics_20260825.zip
```

The ZIP must contain changed files only and preserve repository paths.

---

## Self-Review Results

### Spec coverage

- Inventory factual-only boundary: Task 8 contract coverage.
- Dashboard Alert Insight from AlertCases: Task 2.
- Dashboard Recommended Actions from central Intelligence, max 5: Task 2.
- Canonical Dashboard Alert Insight labels: Task 2.
- Analytics Overview Provider Alert + Anomaly summary: Task 3.
- Object Storage local contextual recommendations: Task 4.
- Provider Alerts vs Anomaly Signals vs recommendations: Task 5.
- Missing-evidence semantics: Tasks 3–5 and runtime coverage in Task 8.
- Notification progress geometry: Task 7.
- Existing UI/HTMX regressions: Task 6.
- Pyright compatibility redirect: Task 6.
- Architecture/future-domain enforcement: Task 1 verifier and architecture docs.
- Full static/runtime/final-release gates: Task 9.

### Placeholder scan

The plan contains no unresolved implementation markers or unspecified code/test steps. Repository-state-dependent archive generation is anchored to the concrete Git tag created in Task 1 Step 0.

### Type consistency

- `get_dashboard_recommendation_findings(domain, asset_key, limit)` is defined once in Task 2 and consumed by both Dashboard domains.
- Object Storage contextual builder signatures are defined once in Task 4 and referenced consistently in later tasks.
- Overview Alerts has its own `overview_alerts` context and does not reuse `_apply_alert_snapshot_context()`, preventing Overview metrics from being overwritten.
- `AnalyticsRecommendation` uses one card shape across Object Storage Analytics pages.

