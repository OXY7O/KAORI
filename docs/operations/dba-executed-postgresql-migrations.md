# DBA-executed PostgreSQL migrations — governed handoff (#1469)

**Status: pre-implementation contract.** This is an operational boundary and review checklist, **not** a claim that the full KAORI Alembic history can be exported as executable SQL. No SQL package is admitted by this document alone.

## Authority

- **External DBA/provider** owns PostgreSQL database creation, login provisioning, TLS, schema/DDL execution authority, backups and restore/recovery. KAORI does not ask for DBA passwords.
- **KAORI application** uses the canonical `DATABASE_URL` with a non-owner, non-superuser runtime principal. Flask, Celery workers and Beat may not run with the DBA or migrator identity.
- **Migration executor** is either a separately authorized, short-lived migration connection for `flask --app run:app db upgrade`, or the DBA's own administrative tooling applying a separately accepted SQL package.
- **KAORI administrator** (the first application user/RBAC bootstrap) is not a PostgreSQL server administrator. Initialize it only once the application tables and approved runtime permissions exist.

## State transitions

1. **External endpoint provisioned** — DBA supplies host, port, database, restricted runtime login and TLS/trust requirements. KAORI validates connectivity without assuming `CREATEDB`, `CREATEROLE`, `SUPERUSER` or schema ownership.
2. **Preflight** — verify actual database name/identity, PostgreSQL version, connectivity, source Alembic revision(s), target release revisions and schema expectations. Validate a current DBA-owned backup, recovery point and operator change authorization. Record only sanitized evidence.
3. **Migration package admission** — review migration revisions from the exact immutable application release. Classify each migration as static offline-compatible, runtime-state-dependent or provider-specific. Package *only* an explicitly reviewed source→target range. Include required DDL/DML, functions/triggers, grant changes, expected `alembic_version` transitions, prerequisites, transaction boundaries and checksums.
4. **DBA change execution** — DBA applies the approved statements using its own credentials, captures sanitized execution results and verifies outcomes. KAORI never receives or logs its privileged password.
5. **Postflight** — KAORI reads committed schema/revision and tests actual `kaori_runtime` privileges, required tables/indexes/triggers, immutable Capsule ledger `SELECT`/`INSERT` and denied `UPDATE`/`DELETE`/`TRUNCATE`, ownership/membership and applicable PostgreSQL durability settings. Do not start workers or Beat until admission succeeds.
6. **Application bootstrap** — initialize/upgrade RBAC and first administrator through an authorized *application* lifecycle after schema and grants are complete.
7. **Release and evidence** — preserve migration artifact SHA, source/target revisions, DBA approval, execution record, backup reference, postflight results and human acceptance with the release evidence.

## Package manifest — required fields

| Field | Meaning |
| --- | --- |
| Release identity | Immutable image digest, source SHA and intended KAORI release version |
| Database target | Sanitized environment/database alias and PostgreSQL major version, never secrets |
| Migration plan | Exact source and target Alembic revision(s) and dependency/order plan |
| SQL payload | Reviewed SQL artifacts, checksums and explicit execution order |
| Data transformations | DML inputs/conditions, expected row effects and data-dependence assessment |
| Preconditions | DBA authorization, backup reference, schema baseline, role/DDL requirements and lock/downtime impact |
| Postconditions | Schema/revision, immutable triggers, effective grants and runtime read-only verification |
| Recovery | Reviewed rollback/restore operation, stop/start boundary and release-state effects |
| Evidence | DBA execution timestamps/result, per-step outcomes, hashes, operator/human acceptance |

## Alembic offline SQL compatibility: known blockers

The current `migrations/env.py` implements `run_migrations_offline()` with `literal_binds=True`, but this **does not establish offline compatibility for all versions**.

Examples requiring explicit engineering review before export:

- `migrations/versions/20260716_repair_kubernetes_discovery_columns.py` calls `sa.inspect(op.get_bind())` against the live schema.
- `migrations/versions/20260817_lifecycle_policy_seed.py` queries existing rows through `bind.execute(...)` before conditional inserts.
- `migrations/versions/20260717_consolidate_authentication_activity.py` conditionally updates permission/role data based on SELECT results.
- `migrations/versions/20261011_capsule_handoff_write_once_ledger.py` creates PostgreSQL trigger functions and depends on dialect-specific state; immutable evidence semantics must be preserved.

Never assume `flask db upgrade --sql` is an admitted production artifact. Use an offline dry-run against a pinned revision range, a representative PostgreSQL copy with matching initial Alembic head and data, review actual emitted SQL, then execute and verify before publishing the DBA handoff. A dynamic migration that cannot be safely represented must fail package admission; it may require reviewed state-specific SQL or an approved DBA-side Python/Alembic executor.

**Forbidden shortcuts:** blind full-history SQL replay onto an existing database; silent table/column omission; using `flask db stamp` to mask absent schema changes; modifying `alembic_version` without proving execution; passing DBA credentials to `DATABASE_URL`; treating CI or a SQL text export alone as UAT.

## Scenarios and disposition

| Scenario | Authority | Expected state |
| --- | --- | --- |
| DevContainer empty bundled PostgreSQL | Local PostgreSQL bootstrap + migrator, operator-triggered | Existing read-only `Initialization Required` until explicit bootstrap; production DBA instructions do not apply |
| Bundled server fresh database | Governed server provisioning and controlled migration runner | Restricted runtime; backup and release-state guards remain |
| External DBA database, empty schema | DBA creates DB/roles and executes admitted SQL or authorizes migrator | KAORI stays Setup Required until schema/grants and first app administrator are admitted |
| External DBA database, existing schema | DBA backup + source→target approved change | No destructive schema reset or automatic grant escalation |
| External DBA supplies only runtime credentials | DBA must execute migration or delegate distinct migrator | **BLOCKED**, not owner fallback |
| Any partially failed migration | DBA/provider recovery authority and frozen release state | **FAIL** until restored or safely completed and independently verified |

## Boundaries and admission

The production adapter currently assumes bundled PostgreSQL and Redis; external PostgreSQL support is **not implemented** by this runbook. See #621 (lifecycle), #622 (external state adapter), #1439 (migration identity), #1440 (external PostgreSQL), and #1469 (DBA SQL package implementation).

Before production use, complete compatibility inventory, SQL export/plan tooling, tests for full revisions and data-dependent migration paths, restricted-role runtime guard, provider-like external PostgreSQL UAT, release governance, Full Admission, DBA acceptance and human promotion review. Never mutate a production database just to prove the procedure.
