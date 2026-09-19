# KAORI Code Health Review and Next Improvement Direction

Date: 2026-07-23

## Executive assessment

KAORI now has a coherent foundation through Domain 20 and a governed application-layer UI for the previously backend-only remediation workflow. The source compiles, the migration graph is linear with one head, architecture boundaries remain within the committed debt baseline, and all runnable contract/migration tests pass.

The platform should **not** add Domain 21 yet. The next cycle should harden resolver delivery semantics, execute the full Python 3.12/PostgreSQL test matrix, then reduce large-module and service-to-form coupling. This keeps KAORI's knowledge → decision → authorization → resolver flow auditable and reversible as more resolver actions are added.

## Completed in this repair

### Migration and schema safety

- Renamed the three oversized resolver revisions so every Alembic revision ID fits `alembic_version.version_num varchar(32)`.
- Preserved a single linear graph ending at `20260723_resolver_readiness`.
- Added a migration contract that fails when any future revision exceeds 32 characters.
- Enforced one global resolver operational-control row by indexing `COALESCE(cluster_id, '__global__')`; a normal unique constraint would permit multiple PostgreSQL `NULL` rows.

### Static typing and null safety

- Narrowed nullable Alertmanager, Prometheus consumer, Kubernetes connection, SSO identity, and capability-definition paths before attribute access.
- Completed TypedDict construction for alert source status and health summaries.
- Replaced SQLAlchemy keyword constructors at the reported warning sites with explicit model creation and field assignment.
- Added protocol-compatible HTTP header typing for Werkzeug `Headers`.
- Normalized Redis Lua arguments, Celery task proxies, dynamic integer conversion, retention domain factories, and runtime adapter Protocol return contracts.
- Moved committed inventory-generation filtering to `app/common/inventory_generation.py` to avoid an Intelligence ↔ Inventory dependency cycle.

### Domain 1–20 operator UI

- Added **Intelligence → Automation Control** at `/intelligence/automation-control`.
- Added five workspaces: Foundation Map, Runbooks & Bindings, Decision Review, Resolver Operations, and Production Readiness.
- Mapped every Domain 1–20 exactly once and retained existing authoritative pages for Domains 1–7.
- Applied KAORI standards: violet hero, permission-driven actions, POST-only mutations, CSRF, PRG feedback, left-aligned data columns, right-aligned actions, compact semantic labels, empty states, and 5/10/25/50 pagination.
- Split the UI into one shell plus five workspace partials to prevent another monolithic template.
- Kept direct resolver dispatch out of the browser surface.

### Runtime governance correction

The worker now evaluates this order before provider mutation:

1. cluster-scoped decision and existing cluster;
2. registered resolver action;
3. active cluster/action deployment policy;
4. target namespace allowlist;
5. policy/worker registry fingerprint parity;
6. executable production-readiness rollout stage;
7. non-production stage cannot target a production cluster;
8. kill switch, maintenance mode, concurrency, rate, and circuit breaker;
9. distributed execution lease;
10. resolver dispatch.

This closes the previous gap where Domain 17 and Domain 20 state existed but was not enforced by the execution worker.

## Current validation result

| Validation | Result |
|---|---|
| Python compile (`app`, `migrations`, `scripts`, `tests`) | Pass |
| Jinja syntax | 407 templates parsed |
| Alembic graph | 83 revisions, one root, one head |
| Architecture verifier | Pass across 2,846 imports |
| Contracts + migration tests | 177 passed |
| Functional UI/runtime tests | Not executable in the supplied sandbox because Flask, Celery, Redis, and Kubernetes client packages are absent |
| PostgreSQL `flask db upgrade` | Must be rerun in the KAORI Python 3.12 devcontainer/staging database |
| Pyright/Pylance | Checker is not installed in the supplied sandbox; source-level fixes and targeted scans were applied |

## Warning disposition

| Diagnostic family | Resolution |
|---|---|
| Nullable Alertmanager passed to `_binding_row` | Guarded in `app/integrations/observability/alert_source/providers/alertmanager/application/presentation.py`. |
| Alert health TypedDict/list invariance | Exact `AlertSourceHealthCheck` and `AlertSourceHealthSummary` annotations in `app/kubernetes/analytics/alerts/health.py`. |
| Incomplete `AlertSourceStatus` | Central complete empty-status constructor in `app/kubernetes/analytics/alerts/snapshots.py`. |
| Optional capability/consumer attributes | Explicit narrowing in capacity, utilization, and workload analytics services. |
| Unknown Kubernetes/provider imports | Correct module paths are used; the symbols exist and compile. |
| SQLAlchemy “No parameter named …” | Reported constructors changed to `Model()` plus assignments. |
| Celery `Proxy` vs `Task` | Cast only at the canonical dispatcher boundary. |
| Redis `eval` argument types | Lua key arguments remain strings and `numkeys` remains the required integer. |
| Werkzeug `Headers` vs `Mapping` | Replaced with a minimal `.get()` Protocol. |
| Flask-Login `login_message=None` | Uses an empty string to disable the default message without violating the declared type. |
| Optional SSO username `.lower()` | Subject and username are normalized safely before allow-list comparison. |
| Empty `set[Never]`, `object` to `int`, retention factory unknown type | Explicit element/factory/parse types added. |
| Missing Knowledge/Intelligence/Resolver modules | Files exist and compile. Treat remaining IDE reports as stale index until Pyright is rerun. |
| `list[str] is not callable` | Targeted AST scan found no annotated list variable called as a function; exact diagnostic cannot be reproduced without its file/line. |

## Existing architecture debt that must not expand

The committed baseline still contains two cycle envelopes:

1. `auth`, `common`, `extensions`, `models`, `notifications`, `rbac`;
2. `alertmanager`, `cluster`, `integrations`, `inventory`, `prometheus`.

It also allows three service-to-form imports:

- `app/integrations/observability/alert_source/providers/alertmanager/application/service.py → app.integrations.observability.alert_source.providers.alertmanager.application.forms`
- `app/prometheus/service.py → app.prometheus.forms`
- `app/access/users/service.py → app.access.users.forms`

No new cycle or service-to-form edge was added. The Automation Control Center was placed in `app/intelligence/automation_control/` specifically to avoid making Intelligence import Knowledge or Resolver.

## Prioritized next work

### P0 — production verification and resolver reliability

1. **Run the full Python 3.12 test suite and real PostgreSQL migration drill.**
   - Environment: KAORI devcontainer or staging clone.
   - Validate upgrade from `20260723_candidate_review`, current head, downgrade, and re-upgrade.
   - Run all functional tests, including `tests/intelligence/test_automation_control_behavior.py` and resolver suites.

2. **Pre-lease journal outcomes — completed in the 24 July foundation hardening slice.**
   - Policy, readiness, configuration, and operational preflight failures now persist retry/dead-letter state and audit evidence.
   - Canonical JobExecution status is updated with the same retry or terminal outcome.

3. **Complete stale-worker redelivery.**
   - Files: `app/intelligence/resolver/orchestration.py`, `app/intelligence/resolver/tasks.py`, Celery/broker deployment evidence.
   - The unused `due_retry_journals()` scaffold was removed. KAORI now relies on `acks_late`, `reject_on_worker_lost`, broker redelivery, and lease recovery, but production enablement still requires evidence that broker retention/visibility preserves the original token-bearing message after worker loss. The alternative is an encrypted expiring execution envelope; plaintext token persistence is forbidden.

4. **Enforce Canary posture, not only Canary evidence.**
   - Files: `app/intelligence/resolver/production_readiness.py`, `app/intelligence/resolver/operations.py`.
   - Validate concurrency limit `1`, approved rate limit, circuit breaker, kill-switch presence, and explicit canary scope before entering or executing Canary.

### P1 — modularity and typed application commands

1. Split the largest modules by use case and stable typed contracts:
   - `app/intelligence/recommendation_engine.py` (~94 KB)
   - `app/integrations/prometheus/query_profiles/kubernetes_v1.py` (~89 KB)
   - `app/kubernetes/analytics/workload/service.py` (~72 KB)
   - `app/kubernetes/analytics/top_consumers/service.py` (~62 KB)
   - `app/kubernetes/analytics/overview/service.py` (~57 KB)
   - `app/reports/generated/service.py` (~57 KB)
   - `app/prometheus/routes.py` (~57 KB)
   - `app/kubernetes/operations/secrets/routes.py` (~56 KB)

2. Replace the three service-to-WTForms imports with application command dataclasses. Routes should map form data to commands; services should accept framework-neutral inputs.

3. Replace broad `dict[str, Any]` Automation Control payloads with TypedDict/dataclass view models and command DTOs.

4. Add eager loading for Automation Control projections (`runbook.revisions`, revision/runbook, binding/revision, journal/decision) and independent pagination for secondary tables currently limited to ten rows.

### P2 — UI, CI, and operational evidence

1. Add browser smoke/accessibility tests for all five Automation Control workspaces, dark/light mode, permission-hidden actions, empty states, and 14-inch viewport behavior.
2. Add Pyright, Ruff, architecture verifier, revision-width contract, full tests, and PostgreSQL migration upgrade/downgrade as mandatory CI gates.
3. Add operator-facing Activity Audit links from each Automation Control row and structured error codes instead of exposing raw exception details as the primary diagnostic.
4. Add metrics for gate-block reasons, policy fingerprint mismatch, readiness stage, dead-letter age, and requeue outcomes.

## Deployment instructions

From the repository root in the KAORI Python 3.12 environment:

```bash
python -m pip install -r requirements/dev.txt
python -m compileall -q app migrations scripts tests
python scripts/verify_migration_graph.py
python scripts/verify_architecture_boundaries.py
pytest -q tests/contracts tests/migrations
pytest -q
flask db current
flask db upgrade
flask db current
```

The failed migration shown by the user occurred while Alembic tried to store a 33-character revision ID in `varchar(32)`. PostgreSQL transactional DDL should leave the prior revision intact, but verify it explicitly. Do **not** manually truncate or edit `alembic_version.version_num`.

Expected corrected head:

```text
20260723_resolver_readiness
```

## Rollback instructions

1. Activate the resolver global kill switch.
2. Disable active resolver deployment policies.
3. Stop consumers for `resolver-execution` and `resolver-maintenance`.
4. Confirm no execution journal is `running`; preserve Activity Audit and readiness evidence.
5. Back up PostgreSQL.
6. Revert the application release.
7. Downgrade only when schema rollback is explicitly required; resolver readiness/control/policy downgrades destroy operational evidence.
8. Independently verify Kubernetes target state after rollback.

## VS Code/Pylance recovery

After applying the patch:

1. Open the KAORI repository root, not a parent or partial folder.
2. Select the project Python 3.12 interpreter from the devcontainer.
3. Install `requirements/dev.txt`.
4. Run **Python: Restart Language Server**.
5. Run **Developer: Reload Window**.
6. Re-run the configured Pyright/Pylance analysis and retain file/line details for any remaining diagnostic.

Do not add missing-module ignores for `app.intelligence.knowledge.*`, `app.models.intelligence`, or `app.intelligence.resolver.contracts`; those modules are present and should resolve when the correct workspace/interpreter is active.
