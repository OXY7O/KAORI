# Report Worker Runtime Reliability Audit — 2026-08-05

## Scope

This audit covers the KAORI report execution path shown in the Activity Deck:

- manual report artifact generation;
- manual execution of one report schedule;
- automatic dispatch of due report schedules;
- Celery queue routing and worker subscription;
- report artifact storage and scheduled delivery hand-off;
- operator-visible worker readiness and queued-job diagnosis.

## Incident evidence

The Activity Deck showed `Generate Report Artifact` and `Dispatch Due Reports` executions in `Queued / Waiting` without progress. The records had valid canonical `JobExecution` identifiers, but the development runtime did not start any worker subscribed to the Reports queue.

## Root causes

1. `.devcontainer/compose.devcontainer.yml` did not define `reports-worker`.
2. `.devcontainer/devcontainer.json` did not include `reports-worker` in `runServices`.
3. Report generation and schedule dispatch hardcoded the queue name `reports` instead of resolving `REPORTS_CELERY_QUEUE` through one owner.
4. Report workspaces displayed static worker-ready copy and did not expose a missing queue consumer.
5. The Activity Deck displayed generic `Waiting` state even when no worker consumed the job queue.
6. Retention and Reports had separate Celery topology inspection implementations.
7. Schedule execution ownership formed a report import cycle through `service -> job_adapter -> tasks -> service`.

## Canonical runtime contract

### Queue ownership

`app/reports/jobs/queue.py` is the only report-domain queue-name resolver. Both dispatch paths call `get_reports_queue_name()`:

- `app/reports/jobs/service.py` for `Generate Report Artifact`;
- `app/reports/schedules/job_adapter.py` for `Dispatch Due Reports`.

Celery routing and worker startup use the same `REPORTS_CELERY_QUEUE` environment variable. The default remains `reports`.

### Worker ownership

The dedicated worker is named `reports@<container-hostname>` and consumes only the configured Reports queue by default.

Development ownership:

- service definition: `.devcontainer/compose.devcontainer.yml`;
- automatic startup: `.devcontainer/devcontainer.json`;
- shared artifact volume: `kaori_instance_data`.

Production ownership:

- service definition: `compose.production.yml`;
- shared artifact volume: `kaori_production_instance`;
- default concurrency: `1`;
- default child recycle limit: `25` tasks.

### Execution flow

Manual generation:

1. Validate the report request.
2. Persist the `Report` record.
3. Create one canonical `JobExecution`.
4. Publish `app.reports.jobs.tasks.generate_report_job` to the Reports queue.
5. Let `reports-worker` render and store the artifact.
6. Finalize the `Report` and persistent operational notification.

Scheduled generation:

1. Celery Beat publishes `app.platform_operations.jobs.tasks.dispatch_scheduled_jobs` to the maintenance queue.
2. The maintenance worker evaluates the `reports.schedule.dispatch` job policy.
3. The canonical dispatcher publishes `app.reports.schedules.tasks.run_report_schedule_job` to the Reports queue.
4. The Reports worker claims due schedule definitions and creates report records.
5. Each generated report is published as a canonical `generate_report_job` on the same Reports queue.
6. The Reports worker renders, stores, and performs configured delivery.

HTTP requests never render report artifacts inline.

## Operator visibility

`app/common/celery_queue_health.py` owns a short-lived shared topology snapshot based on Celery `active_queues`, with `ping` fallback. It reports:

- `Online`: at least one worker consumes the queue;
- `Worker Missing`: workers respond, but none consume the queue;
- `Offline`: no worker responds or Celery is unavailable;
- `Unknown`: topology inspection failed and worker readiness cannot be verified.

The following surfaces use actual queue evidence instead of static readiness:

- Reports Overview;
- Generate Report;
- Report Schedules;
- Report Schedule Dispatcher configuration;
- Activity Deck queued-job cards;
- Retention worker status.

## Existing queued executions

Starting `reports-worker` is sufficient when Redis still contains the Celery messages. Those messages are consumed without creating replacement `JobExecution` records.

When Redis was reset, purged, or restored without the queue payload, the database record can remain queued while no message exists. The operator must:

1. Open **Platform Operations → Jobs & Executions**.
2. Cancel the orphaned queued execution.
3. Run the report or schedule again.
4. Confirm a new task identifier enters `Running` and then a terminal state.

KAORI must not create a second task automatically because generic replay without verified task arguments can violate idempotency and resource ownership.

## Runtime verification

Development:

```bash
docker compose \
  -f compose.yml \
  -f .devcontainer/compose.devcontainer.yml \
  up -d reports-worker maintenance-worker beat

docker compose \
  -f compose.yml \
  -f .devcontainer/compose.devcontainer.yml \
  logs --tail=100 reports-worker
```

Production:

```bash
docker compose -f compose.production.yml up -d \
  reports-worker maintenance-worker beat

docker compose -f compose.production.yml logs --tail=100 reports-worker
```

Queue evidence:

```bash
python scripts/verify_reports_worker_runtime.py
celery --app celery_worker:celery_app inspect active_queues
```

Expected result:

- worker identity starts with `reports@`;
- active queue equals `REPORTS_CELERY_QUEUE`;
- report task names are registered;
- queued report executions transition to `Running` when their broker messages exist.

## Static validation gates

The change is guarded by:

- `scripts/verify_celery_topology.py`;
- `scripts/verify_report_job_standard.py`;
- `scripts/verify_reports_worker_runtime.py` for live worker and task registration evidence;
- Reports contract tests;
- Activity Deck contract tests;
- Python syntax validation;
- architecture-boundary validation;
- internal import-symbol validation;
- YAML and Jinja parsing.

Runtime Compose execution still requires Docker on the target development or production host.
