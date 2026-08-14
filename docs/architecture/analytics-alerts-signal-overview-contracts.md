# Analytics Alerts Signal Overview Contracts

## Purpose

This Batch 3 Slice 8 introduces focused typed contracts for the selected-cluster
signal overview used by KAORI Alerts & Anomalies. It covers the overview payload
and its nested priority, insight, and bar dictionaries while preserving the
ordinary dictionary values consumed by application context, snapshots, Jinja,
reports, dashboards, readiness scoring, and recommendation logic.

This is a contract-only refactor. It does not change alert counting, anomaly
classification, source selection, fallback behavior, priority thresholds,
dominant-signal selection, action guidance, bar calculation, recommendation
behavior, UI wording, or template keys.

## Canonical Contracts

The source of truth is `app/analytics/kubernetes/alerts/contracts.py`.

- `AlertSignalPriority` describes the current normal, warning, or critical
  signal priority presentation.
- `AlertSignalInsight` describes the dominant signal, dominant anomaly, and
  existing action hint.
- `AlertSignalBars` describes the four 12-unit signal bars.
- `AlertSelectedClusterSignalOverview` describes the complete selected-cluster
  signal boundary.

`AlertSelectedClusterSignalOverview` preserves these runtime keys:

```text
cluster_id
cluster_name
source
fallback_used
fallback_reason
connected
active_alerts
critical_alerts
warning_alerts
info_alerts
pending_alerts
resolved_alerts
anomalies
restart_anomalies
not_ready_anomalies
total_signals
priority
insight
bars
```

The nested dictionaries preserve these keys:

```text
priority: level, label, description, icon
insight: dominant_signal, dominant_signal_count, dominant_anomaly,
         dominant_anomaly_count, action_hint
bars: active_alerts, critical_alerts, warning_alerts, anomalies
```

## Updated Boundaries

`app/analytics/kubernetes/alerts/signals.py` now returns
`AlertSelectedClusterSignalOverview` from
`build_selected_cluster_signal_overview()` for both selected and empty cluster
states.

`app/analytics/kubernetes/alerts/readiness.py` now accepts the focused signal overview
contract instead of `dict[str, Any]`. Its scoring behavior is unchanged.

`AlertsSnapshot.priority` and `AlertsSnapshot.insight` now reference
`AlertSignalPriority` and `AlertSignalInsight` directly. The snapshot key set is
unchanged.

The package cutover is complete. Focused consumers import all four contracts
directly from `app.analytics.kubernetes.alerts.contracts`; no compatibility facade remains.

## Behavior Preserved

The following behavior is intentionally unchanged:

- active signals still include alert states `active`, `firing`, and `pending`;
- critical, warning, and info counts still use their existing severity values;
- restart anomalies still match `Pod Restart Spike`;
- not-ready anomalies still match `Pod Not Ready`;
- total signals remain active alerts plus anomaly count;
- any critical alert produces critical priority;
- warning alerts or any anomaly produce warning priority when no critical alert
  exists;
- dominant signal and anomaly continue using the existing candidate order and
  `max()` behavior for ties;
- action-hint precedence remains critical, warning, anomaly, then normal;
- bars still use `build_bar_units()` and retain the 12-unit scale;
- source, fallback, and connectivity values retain their current defaults;
- empty-cluster wording and all nested dictionary values remain unchanged.

No runtime class instances are introduced.

## Validation

Contract tests verify:

- all four focused contracts exist and are imported through canonical modules;
- the selected-cluster builder returns the focused overview contract;
- incident readiness accepts the focused overview contract;
- `AlertsSnapshot` references focused priority and insight contracts;
- empty overview, priority, insight, bars, and snapshot nested dictionaries
  match their typed contract keys exactly.

Functional characterization tests verify:

- populated alert and anomaly inputs produce the existing counts, priority,
  action hint, and dictionary shapes;
- the no-cluster state retains the existing keys, normal priority, and zero
  signal count.

## Follow-On Slice

The multi-cluster comparison rows and resource-link dictionaries are covered by
Batch 3 Slice 9 in
`docs/architecture/analytics-alerts-multi-cluster-resource-links-contracts.md`.
That slice remains separate from provider calls, sorting behavior, bar-width
calculation, link configuration policy, report presentation, and UI redesign.

## Deployment and Rollback

This slice has no database migration, configuration change, background-worker
change, API contract change, or frontend build requirement. Deploy it through
the normal KAORI application release after the alert contract and functional
characterization gates pass in the devcontainer.

Validate before production release with:

```bash
pytest -q \
  tests/contracts/analytics/test_alerts_module_boundaries_contract.py \
  tests/contracts/analytics/test_alerts_typed_contracts.py \
  tests/analytics/test_alerts_characterization.py

bash scripts/quality_gate.sh
```

Rollback by reverting the Slice 8 commit. No database downgrade, data repair,
cache invalidation, or worker-drain procedure is required because runtime
payloads and executable behavior are unchanged.

## Changed Files

```text
app/analytics/kubernetes/alerts/contracts.py
app/analytics/kubernetes/alerts/readiness.py
app/analytics/kubernetes/alerts/signals.py
tests/contracts/analytics/test_alerts_typed_contracts.py
tests/analytics/test_alerts_characterization.py
docs/architecture/analytics-alerts-typed-contracts.md
docs/architecture/analytics-alerts-ownership-readiness-contracts.md
docs/architecture/analytics-alerts-signal-overview-contracts.md
```
