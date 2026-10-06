# KAORI Platform Operations — Data Lifecycle Final Lock v1.2

Status: Final Lock
Date: 2026-08-08
Owner: Platform Operations

v1.2 supersedes v1.1 by making lifecycle coverage explicit without creating new retention engines or provider-specific cleanup jobs.

## Locked Coverage

- `operational_activity` owns the shared `notifications` table lifecycle. It covers the Activity Audit Table, persistent user Notification Center rows, and authentication audit rows. `deck_visible` changes presentation only; it does not remove a persisted row from retention.
- Transient request-local toasts are not persisted and therefore are intentionally outside Data Lifecycle.
- `runtime_observation` owns the shared `integration_runtime_observations` lifecycle. Kubernetes, Prometheus/Thanos, and Alertmanager Recent Runtime Observations all use this provider-neutral source and one lifecycle policy.
- Future integration providers that persist `IntegrationRuntimeObservation` inherit the same lifecycle boundary automatically.
- `job_execution` continues to own canonical execution metadata only; referenced domain datasets remain outside that adapter.

## Presentation Contract

Retention Policies must expose a **Lifecycle Coverage** section for the selected domain. The coverage surface explains the product views included by the source model and an explicit exclusion boundary where relevant. It must use semantic KAORI surfaces and remain dark-mode safe.

The locked workspace order remains:

```text
Retention Policies → Archive History → Archive Storage
```

## Enforcement

```bash
python scripts/verify_data_lifecycle_final_lock.py
pytest -q tests/contracts/platform_operations
```
