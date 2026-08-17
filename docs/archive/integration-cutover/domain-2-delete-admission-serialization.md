# Domain 2 — Delete and Job Admission Serialization

## Problem

A destructive integration transaction previously checked active jobs and then deleted the connection without sharing the job admission lock. A concurrent request could pass admission between dependency inspection and commit, leaving a queued job that referenced a deleted target.

## Decision

KAORI now uses the same PostgreSQL transaction-scoped advisory lock for both operations:

- job admission: `job-resource:<resource_group>`;
- Prometheus and Alertmanager deletion: `integration:<provider>:<instance_id>`;
- Kubernetes deletion: both `kubernetes-cluster:<cluster_id>` and `integration:kubernetes:<connection_id>`.

After waiting for the lock, admission re-reads the target. A target deleted by the transaction that held the lock is rejected before the canonical job is created.

## Runtime behavior

- Admission starts first: deletion waits, then sees the active job and is blocked.
- Deletion starts first: admission waits, then re-checks and rejects the missing source.
- Non-PostgreSQL test environments skip advisory locking; source-existence checks remain active.

## Deployment

No migration or configuration change is required. Deploy web and worker code from the same release.

## Validation

```bash
pytest -q \
  tests/integrations/test_delete_admission_serialization.py \
  tests/contracts/integrations/test_delete_admission_serialization_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert this patch. No database rollback is required.

## Changed files

- `app/jobs/service.py`
- `app/integrations/validation/web.py`
- `app/cluster/sync_jobs.py`
- `app/prometheus/service.py`
- `app/alert_sources/providers/alertmanager/service.py`
- `app/cluster/service.py`
- corresponding functional test, contract test, and this document
