# KAORI Production Deployment

The canonical development and production runbook is maintained in [`RUN.md`](../RUN.md).

Production principles:

- Build the Dockerfile `production` target in CI.
- Deploy an immutable registry image tagged with a version or commit SHA.
- Keep PostgreSQL, Redis, and S3/MinIO credentials outside the repository.
- Validate production environment variables before migration.
- Back up PostgreSQL before every schema migration.
- Run migration once, separately from web startup.
- Run dedicated Celery `inventory` and `maintenance` workers as separate services.
- Use dedicated Redis logical databases for Celery broker, rate limiting, and task results.
- Bootstrap the first administrator only during initial installation.
- Place Gunicorn behind a trusted HTTPS reverse proxy.

## Job Orchestration Services

The Jobs control plane requires three production components for automatic Kubernetes Inventory Sync:

```text
Celery Beat
→ maintenance queue worker
→ inventory queue worker
```

- Celery Beat publishes `app.jobs.tasks.dispatch_scheduled_jobs` once per minute.
- The maintenance worker claims due `job_policies` rows and dispatches registered jobs.
- The inventory worker executes Kubernetes inventory tasks recorded by `JobExecution`; it must not consume maintenance, validation, runtime, analytics, or forecasting queues.
- Set `JOB_POLICY_SCHEDULER_ENABLED=true` on the Beat deployment. Policy intervals remain database-backed and do not require a Beat restart.
- Keep one logical Beat scheduler active. PostgreSQL row locking prevents duplicate policy claims, but a single Beat owner remains the operational standard.
- Development Compose service names are `inventory-worker` and `maintenance-worker`; production uses the same names.
- Default inventory worker tuning is concurrency `1`, max tasks per child `50`, CPU `1.0`, and memory `1g`. Adjust only after measuring sync duration, Kubernetes API pressure, and peak inventory memory.

After deploying this change:

```bash
flask db upgrade
bash scripts/quality_gate.sh --all
```

Verify **Platform Operations → Jobs & Executions → Job Configuration** shows Inventory Sync, the expected eligible fleet, and a future next-run time. Run one manual sync and confirm the same operation appears in the Executions registry with queue `inventory` and operation `inventory_sync_all`.

## Migration Rollback Boundary

Revision `20260724_job_orchestration` migrates the singleton `inventory_sync_policies` row into the generic `job_policies` table and adds `jobs.execute` and `jobs.configure` permissions. Before migration, back up PostgreSQL. If rollback is required before newer job definitions are introduced:

```bash
flask db downgrade 20260724_inventory_sync
```

The downgrade restores the Inventory Sync singleton policy and removes the two new permissions. Do not downgrade after adding additional registered job policies unless their configuration has been exported first, because the legacy table can retain only Inventory Sync.

## Job Cancellation Grace Period

Configure `JOB_CANCEL_GRACE_SECONDS` to control how long KAORI waits for an analytics or forecasting worker to honor cooperative cancellation before the maintenance task escalates with Celery `SIGTERM`.

```env
JOB_CANCEL_GRACE_SECONDS=120
```

The maintenance worker and the target analytics or forecasting workers must share the same Celery control plane. After changing the value, restart web, Beat, maintenance, analytics, and forecasting processes so all components load the same configuration.

## Kubernetes Operations Dashboard Worker Snapshots

The dashboard web process reads committed inventory and analytics snapshots only. This release adds the `dashboard.kubernetes.alerts` dataset and removes live Capacity, Top Consumers, Forecast, and Alerts execution from dashboard HTTP requests.

No database migration or new environment variable is required. Deploy the same image to web, beat, analytics worker, and forecasting worker:

```bash
docker compose -f compose.production.yml up -d --no-deps \
  web \
  analytics-worker \
  forecasting-worker \
  beat
```

Run one manual refresh after deployment:

1. Open **Platform Operations → Jobs & Executions → Job Configuration**.
2. Run **Analytics Data Refresh** once.
3. Run **Forecast Data Refresh** once.
4. Confirm both executions finish successfully before evaluating dashboard completeness.

The Analytics policy always retains:

- `dashboard.kubernetes.alerts` with `cluster_id`;
- `analytics.alerts` with `source=auto`;
- `analytics.capacity` with `time_range=24h`;
- `analytics.top_consumers` with the current cluster scope only.

The Forecast policy always retains `analytics.forecast` with `history_window=30d`. Forecast horizon and model are projected locally from committed historical input. Resource tabs are presentation-only navigation, so tab changes do not create additional provider queries or snapshot rows.

Verify committed rows:

```bash
docker compose -f compose.production.yml exec db psql \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-kaori}" \
  -c "
SELECT
    cluster_id,
    dataset_key,
    parameters_json,
    status,
    generated_at,
    expires_at,
    last_error
FROM analytics_snapshots
WHERE dataset_key IN (
    'dashboard.kubernetes.alerts',
    'analytics.capacity',
    'analytics.top_consumers',
    'analytics.forecast'
)
ORDER BY cluster_id, dataset_key, generated_at DESC;
"
```

Run code validation:

```bash
pytest -q tests/dashboards/test_kubernetes_dashboard_snapshot_flow.py
python scripts/verify_python_syntax.py
```

Runtime verification:

- Web logs must not show Prometheus or Alertmanager calls while `/dashboards/kubernetes/section/*` loads.
- Analytics worker logs own Capacity, Top Consumers, and alert snapshot generation.
- Forecasting worker logs own Forecast generation.
- Missing rows intentionally render an unavailable worker-snapshot state. The dashboard does not perform a live fallback.

Rollback does not require data cleanup. Revert the application commit and redeploy the previous image to web, beat, analytics worker, and forecasting worker. Existing `dashboard.kubernetes.alerts` rows may remain in `analytics_snapshots` because they do not alter the database schema.


## Kubernetes Analytics Dataset Timeouts

KAORI isolates each analytics dataset inside the worker batch so one expensive or unresponsive Prometheus query cannot freeze every following snapshot.

```env
ANALYTICS_DATASET_TIMEOUT_SECONDS=300
FORECASTING_DATASET_TIMEOUT_SECONDS=600
PROMETHEUS_ANALYTICS_QUERY_TIMEOUT_SECONDS=30
PROMETHEUS_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS=120
```

`ANALYTICS_DATASET_TIMEOUT_SECONDS` applies to utilization, capacity, storage, workload, top-consumer, and alert materialization. `FORECASTING_DATASET_TIMEOUT_SECONDS` applies to one forecast history snapshot. The Prometheus query timeouts bound each individual instant or range request so a multi-query dataset cannot wait indefinitely on one provider call. Keep dataset limits below their corresponding Celery task soft limits. After changing them, recreate or restart the analytics and forecasting workers.

Deployment validation:

1. Run Prometheus Full Validation.
2. Run Analytics Data Refresh and confirm a failed dataset does not stop later work items.
3. Run Forecast Data Refresh after the analytics job reaches a terminal state.
4. Open every Kubernetes Analytics page for a ready cluster and for an explicitly selected incomplete cluster.
5. Confirm committed data remains visible with an advisory readiness notice rather than a blank or full-page blocker.

