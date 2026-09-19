# KAORI Platform Operations Final Lock v2.1

Status: Final Lock
Date: 2026-08-08

v2.1 supersedes v2.0 by locking Data Lifecycle coverage semantics. Platform Operations Overview, Jobs & Executions, Archive Storage, and Kubernetes Administration ownership remain unchanged.

Locked refinement:

- Data Lifecycle explicitly covers Activity Audit plus persistent Notification Center records under `operational_activity`.
- Data Lifecycle explicitly covers Kubernetes, Prometheus/Thanos, and Alertmanager Recent Runtime Observations under one provider-neutral `runtime_observation` adapter.
- No provider-specific retention subsystem is introduced.
- The selected Retention Policy exposes a Lifecycle Coverage evidence section.

See `KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_2.md` for the dedicated contract.
