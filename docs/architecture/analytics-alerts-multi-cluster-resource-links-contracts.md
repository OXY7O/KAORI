# Analytics Alerts Multi-Cluster and Resource-Link Contracts

## Purpose

This Batch 3 Slice 9 introduces focused typed contracts for the multi-cluster
signal comparison rows and operational resource-link dictionaries produced by
`app/kubernetes/analytics/alerts/signals.py`.

This is a contract-only refactor. It preserves the ordinary dictionaries and
lists consumed by application context, templates, and
report code. It does not change provider calls, source fallback, signal counts,
sorting, bar-width calculation, link availability, wording, or UI behavior.

## Canonical Contracts

The source of truth is `app/kubernetes/analytics/alerts/contracts.py`.

- `AlertClusterSignalComparisonRow` describes one multi-cluster comparison row.
- `AlertResourceLink` describes one resource-link card.
- `AlertResourceLinks` describes the complete Alertmanager, runbook, and contact
  point link dictionary.

`AlertClusterSignalComparisonRow` preserves these runtime keys:

```text
cluster_id
cluster_name
active_alerts
critical_alerts
warning_alerts
anomalies
total_signals
connected
resolved_source
fallback_used
bar_width
```

`AlertResourceLinks` preserves these top-level keys:

```text
alertmanager
runbook
contact_point
```

Every resource link requires:

```text
configured
label
url
description
```

The existing contact-point item additionally retains optional `name` and
`email` fields. No new fields are emitted for Alertmanager or runbook links.

## Updated Boundaries

`build_cluster_signal_overview()` now returns
`list[AlertClusterSignalComparisonRow]`.

`build_resource_links()` now returns `AlertResourceLinks`.

The package migration is complete. All three contracts are imported directly
from `app.kubernetes.analytics.alerts.contracts`; no compatibility facade remains.

## Behavior Preserved

The following behavior is intentionally unchanged:

- each cluster still loads alerts through `load_alerts_by_source()`;
- anomaly rows still come from `build_anomalies()` with the existing all-severity
  and unfiltered arguments;
- active alerts still include `active`, `firing`, and `pending` states;
- critical and warning counts retain their existing severity comparisons;
- total signals remain active alerts plus anomaly count;
- source connectivity, resolved source, and fallback flags retain their current
  defaults;
- maximum signal count still determines relative bar width;
- all-zero overviews still assign width zero to every row;
- when any cluster has signals, every row still receives at least eight
  percent width, including zero-signal rows;
- sorting still uses critical count, total signals, and cluster name in reverse
  order;
- Alertmanager configuration still requires both configured state and endpoint;
- runbook and contact-point links remain unconfigured placeholders;
- all labels, descriptions, URLs, and template keys remain unchanged.

No runtime class instances are introduced.

## Validation

Contract tests verify:

- all three focused contracts exist and are consumed through canonical modules;
- both builders use the focused return annotations;
- the comparison-row literal keys match the typed contract;
- resource-link top-level and nested dictionaries match their required and
  optional key sets.

Functional characterization tests verify:

- comparison rows retain counts, source metadata, reverse sorting, and relative
  bar widths across multiple clusters;
- configured Alertmanager links retain their endpoint;
- runbook and contact-point placeholders retain their current values and
  dictionary shapes.

## Follow-On Slice

The next focused contract reduction should evaluate normalized anomaly rows in
`anomalies.py`. That work must remain separate from Prometheus queries, anomaly
thresholds, severity assignment, filtering, recommendation behavior, and UI
redesign.

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

Rollback by reverting the Slice 9 commit. No database downgrade, data repair,
cache invalidation, or worker-drain procedure is required because runtime
payloads and executable behavior are unchanged.

## Changed Files

```text
app/kubernetes/analytics/alerts/contracts.py
app/kubernetes/analytics/alerts/signals.py
tests/contracts/analytics/test_alerts_typed_contracts.py
tests/analytics/test_alerts_characterization.py
docs/architecture/analytics-alerts-typed-contracts.md
docs/architecture/analytics-alerts-signal-overview-contracts.md
docs/architecture/analytics-alerts-multi-cluster-resource-links-contracts.md
```
