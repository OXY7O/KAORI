# Automation Control Center UI

## Purpose

The Automation Control Center provides one governed operator surface for KAORI
Domain 1–20 without collapsing their domain boundaries. Existing domain-specific
pages remain authoritative for Authentication, Jobs, Kubernetes, Prometheus,
Alertmanager, Integrations, Recommendations, Alert Intelligence, and Rule
Catalog. The new application-layer workspace consolidates the backend-only
operational paths introduced by Domains 8–20.

Route: `GET /intelligence/automation-control`

Navigation: **Intelligence → Automation Control**

Ownership boundary: `app/automation_control/` is an application orchestration
layer. Knowledge, Intelligence, Resolver, and Integration domains do not import
it. This prevents a cross-domain dependency cycle while preserving their public
service contracts.

## Workspace structure

| Workspace | Domain coverage | Operator capability |
|---|---:|---|
| Foundation Map | 1–20 | Shows the domain, layer, existing/new operator surface, and persisted safety evidence. |
| Runbooks & Bindings | 12–14 | Creates stable runbooks, immutable draft revisions, publication validation, withdrawal, and deterministic alert bindings. |
| Decision Review | 8–9, 15, 18 | Reviews non-executable candidates, creates immutable decisions, records approval/rejection, and observes execution journals. |
| Resolver Operations | 10–11, 16–19 | Manages registry-aware deployment policy, global/cluster operational controls, resolver metrics, and explicit dead-letter requeue. |
| Production Readiness | 20 | Records the complete readiness checklist and advances rollout through Disabled → Shadow → Non-Production → Canary → Production. |

The page shell includes one partial for each workspace. This is a deliberate
maintainability boundary: changes to one operator flow do not require editing a
single monolithic template.

## Mutation boundaries

All state changes are POST-only, CSRF-protected, permission-gated, audited by the
owning domain service, and returned through POST/Redirect/GET with KAORI transient
feedback.

| Capability | Required permission |
|---|---|
| View workspace | `intelligence.view` |
| Create runbook/revision/binding | `knowledge.runbooks.manage` |
| Publish or withdraw revision | `knowledge.runbooks.publish` |
| Promote or dismiss candidate | `intelligence.decisions.create` |
| Approve or reject decision | `intelligence.decisions.approve` |
| Manage policy/control/readiness/dead letters | `intelligence.decisions.execute` |

The UI deliberately does **not** expose direct resolver dispatch. Resolver
workers enforce the immutable decision token, registered action, active deployment
policy, namespace allowlist, registry fingerprint parity, executable rollout
stage, cluster-environment boundary, and Domain 19 operational controls before
acquiring the distributed execution lease.

## Deployment-policy validation

An active deployment policy is accepted only when:

1. the selected cluster exists;
2. the resolver action is present in the committed registry;
3. at least one explicit namespace is allow-listed; and
4. an optional registry fingerprint matches the registered action.

A disabled policy may remain stored without an allow-list so operators can stage
configuration before activation.

## Operational-control uniqueness

KAORI permits one global resolver control (`cluster_id IS NULL`) and one control
per cluster. PostgreSQL ordinary unique constraints allow multiple `NULL` values,
so migration `20260723_resolver_controls` uses an expression unique index over
`COALESCE(cluster_id, '__global__')`. The SQLAlchemy model declares the same index
so fresh schema generation and Alembic upgrades retain identical semantics.

## Files changed

- `app/automation_control/__init__.py`: application-layer package boundary.
- `app/automation_control/presentation.py`: Domain 1–20 map, pagination, read models, policy validation, and UI-safe row projection.
- `app/automation_control/routes.py`: GET workspace plus POST-only governed mutation boundaries.
- `app/templates/intelligence/automation_control.html`: KAORI Violet shell, workspace navigation, shared feedback, and partial inclusion.
- `app/templates/intelligence/partials/automation_control/_overview.html`: Domain 1–20 foundation map.
- `app/templates/intelligence/partials/automation_control/_runbooks.html`: runbook, revision, and alert-binding workflow.
- `app/templates/intelligence/partials/automation_control/_decisions.html`: candidate and immutable-decision review workflow.
- `app/templates/intelligence/partials/automation_control/_operations.html`: deployment policy, controls, journals, and resolver observations.
- `app/templates/intelligence/partials/automation_control/_readiness.html`: readiness evidence and staged rollout workflow.
- `app/templates/components/navigation/intelligence_menu.html`: Intelligence navigation entry.
- `app/common/navigation.py`: breadcrumb registration.
- `tests/contracts/intelligence/test_automation_control_ui_contract.py`: source-level safety, coverage, and template-boundary contract.
- `tests/intelligence/test_automation_control_behavior.py`: functional behavior for pagination and deployment-policy guardrails.
- `tests/migrations/test_migration_graph_contract.py`: migration graph, revision-width, and global-control uniqueness contracts.

## Deployment validation

Run in this order from the repository root:

```bash
python -m pip install -r requirements/dev.txt
python -m compileall -q app migrations scripts tests
python scripts/verify_migration_graph.py
python scripts/verify_architecture_boundaries.py
pytest -q tests/contracts tests/migrations
pytest -q tests/intelligence/test_automation_control_behavior.py
flask db current
flask db upgrade
flask db current
```

After deployment:

1. Open **Intelligence → Automation Control**.
2. Confirm all five workspaces load for a user with `intelligence.view`.
3. Confirm mutation controls are absent when the user lacks the associated permission.
4. Create a draft runbook revision and verify publication remains blocked when resolver capability/profile validation fails.
5. Attempt an active deployment policy without namespaces and confirm KAORI rejects it.
6. Record incomplete readiness evidence and verify Canary/Production remain blocked.
7. Verify an Activity Audit Log entry is present for every successful mutation.

## Rollback

Application rollback is safe because the UI does not alter execution semantics.
Revert the application commit and retain the resolver tables when operational
evidence must be preserved. For a full schema rollback, perform a database backup
first and downgrade from `20260723_resolver_readiness` through the resolver
migrations in reverse order. Downgrade removes readiness, operational-control,
and deployment-policy records and therefore destroys rollout evidence.

Do not manually truncate Alembic revision IDs in `alembic_version`. The failed
upgrade that exposed the 32-character limit runs inside PostgreSQL transactional
DDL; verify the current revision and rerun the corrected migration graph.
