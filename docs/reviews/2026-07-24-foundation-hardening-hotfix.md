# KAORI Foundation Hardening Hotfix

Date: 2026-07-24

## Scope

This hotfix corrects defects found while validating the foundation-hardening patch before Inventory and Analytics expansion.

## Corrected Defects

1. `app/commands/integrations.py` imported `dispatch_integration_runtime_refresh` through a package-level lazy façade. The command now imports the canonical implementation directly from `app.integrations.runtime.monitoring`, and the package façade was removed.
2. `_sync_kubernetes_runtime()` referenced `connection` before initialization. The function now resolves the existing connection from `cluster.kubernetes_connection` before canonical instance convergence.
3. Storage report export instantiated `PrometheusConsumer` without importing it.
4. Ruff import-order, unused-import, and multiple-statements violations reported during validation were corrected.

## Validation

Run from the KAORI Dev Container:

```bash
ruff check app tests scripts migrations
python -m compileall -q app tests scripts migrations
python scripts/verify_architecture_boundaries.py
python scripts/verify_celery_topology.py
python scripts/verify_code_health.py
python scripts/verify_migration_graph.py
pytest -q tests/contracts/architecture/test_foundation_hardening_hotfix_contract.py
pytest -q -m "not debug"
```

## Rollback

Revert the hotfix commit. No migration, configuration, or persistent-data rollback is required.

## Files Changed

- `app/kubernetes/analytics/capacity/service.py`
- `app/kubernetes/analytics/forecast/service.py`
- `app/kubernetes/analytics/storage/service.py`
- `app/kubernetes/analytics/top_consumers/service.py`
- `app/kubernetes/analytics/workload/service.py`
- `app/bootstrap/blueprints.py`
- `app/kubernetes/cluster/service.py`
- `app/commands/integrations.py`
- `app/integrations/runtime/__init__.py`
- `app/inventory/resources/common.py`
- `app/models/resolver.py`
- `app/intelligence/resolver/orchestration.py`
- `tests/contracts/architecture/test_foundation_hardening_hotfix_contract.py`
- `tests/intelligence/test_decision_candidate_review.py`
- `tests/knowledge/test_alert_runbook_matching.py`
- `tests/knowledge/test_versioned_runbook_workflow.py`
- `tests/resolver/test_resolver_operational_controls.py`
