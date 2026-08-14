# Analytics Alerts Decomposition Pilot

## Purpose

Analytics Alerts is the first KAORI large-service decomposition pilot. The change preserves the existing page, dashboard, and reporting contracts while replacing one 4,637-line implementation file with explicit responsibility modules.

This is a behavior-preserving modular-monolith refactor. It does not introduce a new service, database, queue, route, or external API.

## Previous Boundary

Before this pilot, `app/analytics/kubernetes/alerts/service.py` owned all of the following:

- filter and pagination normalization;
- cluster and namespace selection;
- Alertmanager and Prometheus source loading;
- provider-payload normalization;
- anomaly queries and normalization;
- integration and source-health presentation;
- routing and grouping summaries;
- silence matching;
- inhibition visibility;
- ownership, runbook, and contact extraction;
- incident-readiness scoring;
- signal overview composition;
- page context orchestration;
- dashboard and report snapshots.

The file had too many independent reasons to change and made source-provider behavior difficult to test in isolation.

## Canonical Module Layout

```text
app/analytics/kubernetes/alerts/
├── contracts.py      filter, pagination, and public option contracts
├── selection.py      cluster and namespace selection
├── metrics.py        Prometheus metric payload helpers
├── sources.py        Alertmanager/Prometheus loading and alert normalization
├── anomalies.py      anomaly loading, normalization, and filtering
├── health.py         integration status, source health, and summary
├── routing.py        receiver and grouping analysis
├── silences.py       Alertmanager silence loading and matcher evaluation
├── inhibition.py     inhibition visibility derived from alert metadata
├── ownership.py      owner, runbook, and contact resolution
├── readiness.py      incident-readiness scoring
├── signals.py        resource links and signal overview composition
├── application.py    interactive page-context orchestration
└── snapshots.py      dashboard/report snapshot orchestration
```

## Dependency Direction

```text
HTTP / Dashboard / Report Adapter
                ↓
application.py or snapshots.py
                ↓
focused domain modules
                ↓
sources.py / anomalies.py / silences.py
                ↓
Prometheus and Alertmanager provider façades
```

Rules:

1. `application.py` and `snapshots.py` do not issue provider requests directly.
2. Provider payload normalization stays in `sources.py` and `anomalies.py`.
3. Pure policy functions remain independent of Flask request state.
4. Internal KAORI consumers import focused modules; `service.py` is retired.
5. New Alerts behavior must be added to the owning module and covered by characterization tests.

## Compatibility Cutover

`app.analytics.kubernetes.alerts.service` was removed after every known KAORI consumer moved to canonical modules:

- web route → `application.get_alerts_context`;
- report section → `application.get_alerts_context`;
- dashboard source reads → `sources.load_alerts_by_source`.

The façade can be removed when repository-wide and downstream consumers no longer depend on it. Removal must be a dedicated change with an architecture-contract update.

## Characterization Coverage

`tests/analytics/test_alerts_characterization.py` freezes the current behavior of:

- page and per-page normalization;
- Alertmanager normalization;
- Prometheus fallback normalization;
- receiver and group counting;
- silence equality, regex, and negative matching;
- ownership/runbook/contact precedence;
- incident-readiness penalties;
- application context shape and orchestration wiring.

These tests are intentionally based on current behavior. Future behavior changes must update the implementation and expected contract deliberately in the same commit.

## Validation

```bash
python -m ruff check app migrations tests scripts
python scripts/verify_architecture_boundaries.py
pytest -q tests/contracts/analytics/test_alerts_module_boundaries_contract.py
pytest -q tests/analytics/test_alerts_characterization.py
bash scripts/quality_gate.sh --all
```

## Next Step

The next Batch 3 slice should introduce typed normalized alert and source-status contracts. That change should occur after this structural split is merged and observed, rather than being combined with the package decomposition.
