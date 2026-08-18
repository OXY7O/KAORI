# KAORI Deployment

Use an immutable tagged image and a production environment file based on `.env.production.example`. `KAORI_IMAGE` and `APP_VERSION` must identify the same release. The canonical running guide is `docs/RUNNING.md`; this document records deployment-specific contracts and worker details.

## Production Release Startup

Back up PostgreSQL before applying a new release. Then validate configuration, migrate, and start the complete production stack:

```bash
docker compose -f compose.production.yml run --rm validate
docker compose -f compose.production.yml run --rm migrate
docker compose -f compose.production.yml up -d
docker compose -f compose.production.yml ps
```

Confirm the `web` service becomes healthy and review the logs before opening traffic:

```bash
docker compose -f compose.production.yml logs --tail=100 web
```

After the stack is running, verify worker queue ownership and run the runtime-aware final gate from a release checkout when the environment provides its required services:

```bash
python scripts/verify_final_release.py --all --runtime
```

Rollback must use a previously approved immutable image and a migration plan appropriate to the schema revision. Do not point `KAORI_IMAGE` at an unversioned `latest` tag.

## Production Principles

The canonical development and production runbook is `docs/RUNNING.md`.


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

## Metrics Source Hard-Cut Deployment

Revision `20260817_metrics_source_v2` is an atomic namespace/schema cutover from the retired product-owned metrics integration to the provider-neutral **Metrics Source** contract. It renames the metrics table to `metrics_sources`, rewrites canonical integration/runtime/job/event identities to `metrics_source`, and persists concrete product identity only in `provider_key`. Active runtime code intentionally provides no dual-read path, route alias, compatibility redirect, or model wrapper for the retired namespace.

Do not run old and new KAORI web/worker versions concurrently across this migration. Old integration-validation/runtime messages can contain the retired provider identifier in their serialized task arguments, and a database migration cannot rewrite messages already waiting in Redis.

Deployment sequence:

1. Back up PostgreSQL and record the current Alembic revision.
2. Stop Celery Beat and stop/drain the old web, `integration-validation`, and `integration-runtime` processes so no old code can enqueue or consume integration work during the cutover.
3. Confirm the `integration-validation` and `integration-runtime` queues contain no pending messages created by the old release. If the broker is purged instead of drained, reconcile any corresponding queued `JobExecution` records through the governed Jobs & Executions workflow before retrying those operations.
4. Deploy the new image/code to all components, but keep integration workers stopped.
5. Run the migration exactly once:

```bash
flask db upgrade
```

6. Start the new web process, `integration-validation` worker, `integration-runtime` worker, analytics/forecasting workers, maintenance worker, and Beat from the same release image.
7. Run **Metrics Source Full Validation** for every enabled source, then validate enabled Kubernetes/Object Storage bindings and run one analytics refresh for each affected domain.
8. Verify **Integrations → Observability → Metrics Sources** shows each provider through its concrete `provider_key` label while runtime, jobs, routing, notifications, Analytics, Reports, Intelligence, Kubernetes, and Object Storage use the global Metrics Source category.

For a provider that uses the existing registered adapter/query contract, future onboarding is provider-catalog work rather than a global schema/route/consumer refactor. A provider with a genuinely different API or query language adds a backend adapter and adapter-scoped validation/query profiles while retaining the same `metrics_source` table, binding model, route family, runtime namespace, and consumer source category.

## Job Orchestration Services

The Jobs control plane requires three production components for automatic Kubernetes Inventory Sync:

```text
Celery Beat
→ maintenance queue worker
→ inventory queue worker
```

- Celery Beat publishes `app.platform_operations.jobs.tasks.dispatch_scheduled_jobs` once per minute.
- The maintenance worker claims due `job_policies` rows and dispatches registered jobs.
- The inventory worker executes Kubernetes inventory tasks recorded by `JobExecution`; it must not consume maintenance, validation, runtime, analytics, or forecasting queues.
- Set `JOB_POLICY_SCHEDULER_ENABLED=true` on the Beat deployment. Policy intervals remain database-backed and do not require a Beat restart.
- Keep one logical Beat scheduler active. PostgreSQL row locking prevents duplicate policy claims, but a single Beat owner remains the operational standard.
- Development Compose service names are `inventory-worker` and `maintenance-worker`; production uses the same names.
- Data Lifecycle retention defaults to `RETENTION_CELERY_QUEUE=maintenance`, so it uses the existing `maintenance-worker`; do not deploy a second retention worker unless the retention queue is intentionally separated.
- `RETENTION_RETRY_DELAY_SECONDS` controls the single bounded retry delay for transient retention connectivity failures (default `60`). Exhausted or non-retryable failures remain visible in Jobs & Executions and require operator review.
- Analytics materialization rows use the `analytics_snapshot` lifecycle domain by default: 30-day hot retention, 180-day verified archive retention, and a 04:15 schedule. Pending/current/stale-but-serveable snapshots remain protected until stale grace and hot retention have both elapsed.
- Default inventory worker tuning is concurrency `2`, prefetch multiplier `1`, and max tasks per child `50`. Two execution slots prevent a long Kubernetes inventory sync from blocking Object Storage Inventory Sync (or vice versa) when **Sync All Inventory** dispatches both domains to the shared `inventory` queue. Adjust only after measuring sync duration, Kubernetes API pressure, and peak inventory memory.

After deploying this change:

```bash
flask db upgrade
bash scripts/quality_gate.sh --all
```

Verify **Platform Operations → Jobs & Executions → Job Configuration** shows Kubernetes Inventory Sync, the expected eligible fleet, and a future next-run time. Run one manual sync and confirm the same operation appears in the Executions registry with queue `inventory` and operation `sync_kubernetes_inventory`.

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
pytest -q tests/kubernetes/dashboard/test_kubernetes_dashboard_snapshot_flow.py
python scripts/verify_python_syntax.py
```

Runtime verification:

- Web logs must not show Metrics Source or Alertmanager calls while `/dashboards/kubernetes/section/*` loads.
- Analytics worker logs own Capacity, Top Consumers, and alert snapshot generation.
- Forecasting worker logs own Forecast generation.
- Missing rows intentionally render an unavailable worker-snapshot state. The dashboard does not perform a live fallback.

Rollback does not require data cleanup. Revert the application commit and redeploy the previous image to web, beat, analytics worker, and forecasting worker. Existing `dashboard.kubernetes.alerts` rows may remain in `analytics_snapshots` because they do not alter the database schema.


## Kubernetes Analytics Dataset Timeouts

KAORI isolates each analytics dataset inside the worker batch so one expensive or unresponsive Metrics Source query cannot freeze every following snapshot.

```env
ANALYTICS_DATASET_TIMEOUT_SECONDS=300
FORECASTING_DATASET_TIMEOUT_SECONDS=600
METRICS_SOURCE_ANALYTICS_QUERY_TIMEOUT_SECONDS=30
METRICS_SOURCE_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS=120
```

`ANALYTICS_DATASET_TIMEOUT_SECONDS` applies to utilization, capacity, storage, workload, top-consumer, and alert materialization. `FORECASTING_DATASET_TIMEOUT_SECONDS` applies to one forecast history snapshot. The Metrics Source query timeouts bound each individual instant or range request so a multi-query dataset cannot wait indefinitely on one provider call. Keep dataset limits below their corresponding Celery task soft limits. After changing them, recreate or restart the analytics and forecasting workers.

Deployment validation:

1. Run Metrics Source Full Validation for each bound source.
2. Run Analytics Data Refresh and confirm a failed dataset does not stop later work items.
3. Run Forecast Data Refresh after the analytics job reaches a terminal state.
4. Open every Kubernetes Analytics page for a ready cluster and for an explicitly selected incomplete cluster.
5. Confirm committed data remains visible with an advisory readiness notice rather than a blank or full-page blocker.


## Reports Worker Deployment

Report generation is not executed by Gunicorn, the generic inventory worker, or the maintenance worker. Deploy the dedicated `reports-worker` with the same image, database, broker, result backend, artifact-storage volume, and `REPORTS_CELERY_QUEUE` value used by the web process.

```bash
docker compose -f compose.production.yml up -d --no-deps \
  web \
  reports-worker \
  maintenance-worker \
  beat
```

Verify the process identity and queue subscription:

```bash
docker compose -f compose.production.yml ps reports-worker
docker compose -f compose.production.yml logs --tail=100 reports-worker
docker compose -f compose.production.yml exec web \
  python scripts/verify_reports_worker_runtime.py
```

The inspection must show `reports@...` consuming the configured Reports queue. The following tasks must route to that same queue:

- `app.reports.jobs.tasks.generate_report_job`
- `app.reports.schedules.tasks.run_report_schedule_job`

KAORI now resolves the queue from `REPORTS_CELERY_QUEUE` at dispatch time; a custom queue name therefore cannot diverge between the worker and `JobExecution.queue_name`. The Reports Overview, Generate Report, Report Schedules, Job Configuration, and Activity Deck surface worker/queue readiness instead of reporting a static Ready state.

Queued records created while the worker was stopped will continue when Redis still contains their Celery messages. When the broker was reset or purged, cancel the orphaned queued execution from **Platform Operations → Jobs & Executions**, then run the report or schedule again so KAORI creates a new canonical task identifier.
