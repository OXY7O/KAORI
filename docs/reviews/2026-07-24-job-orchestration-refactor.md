# Job Orchestration Refactor — 2026-07-24

## Objective

Move Inventory Sync out of Settings and establish one scalable Jobs control plane for Inventory, report generation, analytics materialization, forecasting, retention, reconciliation, and future background work.

## Final Ownership

```text
Platform Operations → Jobs & Executions
├── Executions
└── Job Configuration
```

`app.jobs` owns registration, generic policy, admission, canonical dispatch, `JobExecution`, progress, cancellation, recovery, and UI orchestration. Feature logic remains in its source domain. Inventory collection and generation promotion therefore remain under `app.inventory` and `app.cluster`.

## Canonical Dispatch

```text
Manual action / Celery Beat
→ JobDefinition registry
→ owning-domain permission and target resolution
→ create or attach canonical JobExecution
→ dedicated Celery queue
→ domain executor
→ progress and terminal result
```

The first definition is `kubernetes.inventory.sync`. Both scheduled and manual fleet synchronization resolve the same eligible Kubernetes fleet and use the same deduplication group `kubernetes-inventory:global`.

## Database Change

Migration `20260724_job_orchestration`:

- creates generic `job_policies`;
- migrates the existing `inventory_sync_policies` singleton;
- drops the legacy singleton table;
- adds `jobs.execute` and `jobs.configure`;
- maps existing default and custom-role authority into the new permissions.

Current automatic policies use validated intervals from 5 to 1,440 minutes. Cron is intentionally not exposed until a real cron scheduler contract and behavioral test exist.

## Runtime Safety

- Celery Beat checks policies every minute but does not own the actual interval.
- Due rows are claimed with `FOR UPDATE SKIP LOCKED`.
- Invalid policies are disabled rather than crashing the recurring dispatcher.
- No `JobExecution` is created when no Kubernetes cluster has an enabled canonical binding.
- Active manual and scheduled fleet requests attach to one canonical execution.
- Each cluster uses its own database lock and atomic inventory generation commit.
- Failed collection preserves the previously committed generation.

## RBAC

- `jobs.view`: executions and configuration catalog visibility.
- `jobs.execute`: manual registered-job dispatch.
- `jobs.configure`: automatic policy changes.
- `jobs.cancel`: supported execution cancellation.
- Inventory Sync additionally requires `clusters.sync`.

## Deployment

Required services:

```text
beat
maintenance-worker   → maintenance queue
inventory-worker     → inventory queue
```

Development and production Compose use the same worker service names. The former generic `worker` service is retired so provider-heavy inventory collection cannot delay policy dispatch and stale-job recovery. Enable `JOB_POLICY_SCHEDULER_ENABLED=true`, run `flask db upgrade`, recreate the Compose services, then validate the Jobs Configuration page and one manual Inventory Sync execution.

## Validation

Required release commands:

```bash
bash scripts/quality_gate.sh --all
flask db upgrade
```

Operational validation:

1. Open **Platform Operations → Jobs & Executions → Job Configuration**.
2. Confirm Inventory Sync is enabled and the eligible fleet is correct.
3. Change the interval and confirm the next-run time resets without restarting Beat.
4. Run **Sync All Inventory**.
5. Confirm `inventory_sync_all` appears in Executions on queue `inventory`.
6. Confirm a concurrent manual or scheduled request attaches to the active execution.
7. Disable a Kubernetes binding and confirm the cluster is excluded before admission.

## Rollback

Before migration, back up PostgreSQL. To return to the Inventory Sync singleton while no additional policies exist:

```bash
flask db downgrade 20260724_inventory_sync
```

The downgrade cannot preserve future non-inventory policies because the legacy table supports only one Inventory Sync row.

## Changed Areas

- `app/jobs/`: registry, definitions, policies, scheduler, routes, configuration UI, dispatcher.
- `app/inventory/` and `app/cluster/`: Inventory Sync domain adapter and Quick Action dispatch.
- `app/models/job.py`: generic `JobPolicy`.
- `app/rbac/`: execution and configuration permissions.
- `app/templates/jobs/`: Executions and Job Configuration tabs.
- `.devcontainer/compose.devcontainer.yml`, `.devcontainer/devcontainer.json`, and `compose.production.yml`: dedicated inventory and maintenance worker topology.
- navigation, Welcome catalog, deployment environment examples, and architecture documentation.

## Retired Areas

- `app/settings/inventory_sync/`
- `app/templates/settings/inventory_sync/`
- `app/inventory/schedule.py`
- `app/inventory/tasks.py`
- provider-owned Jobs routes and templates under `app/integrations/`
