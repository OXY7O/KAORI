# KAORI Application Package Standard

## Decision

KAORI is a **modular monolith with domain-first MVC/application layers**. The repository does not use a global `models/`, `views/`, `controllers/` split for application behavior because that would scatter one feature across unrelated top-level directories. SQLAlchemy ORM models remain centralized in `app/models/` for Alembic discovery, relationships, and import-cycle control.

The canonical navigation rule for code is:

`bounded context -> capability/integration type -> provider or managed asset -> application layer`

A developer should be able to start from the product concept and predict the package path without memorizing a product-specific exception.

## Top-level bounded contexts

- `app/access/` — authentication, users, identity providers, RBAC, roles, permissions, Activity Audit.
- `app/integrations/` — provider-neutral integration contracts, providers/adapters, registration and binding workspaces.
- `app/kubernetes/` — Kubernetes managed-asset lifecycle, dashboard, inventory, analytics, governance, and live operations.
- `app/storage/` — infrastructure storage managed assets; Object Storage inventory/analytics live here.
- `app/intelligence/` — recommendations, Alert Intelligence, Automation Control, Knowledge, and resolver workflows.
- `app/platform_operations/` — jobs/executions, operational notifications, health, Data Lifecycle, and operational control surfaces.
- `app/reports/`, `app/settings/`, `app/welcome/` — independent application capabilities.
- `app/artifact_storage/` — KAORI artifact persistence. This must not be confused with infrastructure `app/storage/`.
- `app/common/`, `app/security/`, `app/definitions/`, `app/extensions/`, `app/bootstrap/`, `app/commands/`, `app/config/` — shared/kernel infrastructure only.

Product implementations must not reappear as top-level packages. Provider-specific code belongs below `providers/<provider>/`; protocol/API code belongs below `adapters/<adapter>/`.

## Domain-first MVC mapping

Within a feature package, use the smallest useful subset of these files:

- `routes.py` — **Controller**: authorization, HTTP parsing, service invocation, response/render selection.
- `forms.py` — input parsing and validation.
- `service.py` — application/use-case orchestration and transaction intent.
- `policy.py` — business/security invariants and admission decisions.
- `repository.py` — persistence queries and ORM access.
- `presentation.py` — **View model** construction only; no business mutation.
- `contracts.py` — DTO/dataclass/schema contracts.
- `tasks.py` — worker entry point; workers call service/application logic instead of duplicating it.
- `providers/` — product-specific behavior.
- `adapters/` — protocol/API implementation.
- `templates/<same-domain-path>/` — **View**.

Not every feature needs every file. Empty ceremony is forbidden; add a layer only when it owns real behavior.

## Dependency direction

Preferred request flow:

`route -> form/contract -> service/policy -> repository/model or adapter -> presentation -> template`

Preferred worker flow:

`task -> service/policy -> repository/model or adapter`

New repository modules may not depend on Flask request globals, `current_user`, redirects, or template rendering. New service modules may not render templates. New presentation modules may not mutate the database.

Some historical route modules still perform direct ORM persistence and one historical presentation module still mutates persistence. Those files are explicitly listed in `docs/architecture/mvc-debt-baseline.json`. The baseline may shrink but must never grow.

## Physical namespace rules

Canonical examples:

- `app/access/users/` <-> `app/templates/access/users/`
- `app/access/authentication/` <-> `app/templates/access/authentication/`
- `app/kubernetes/analytics/` <-> `app/templates/kubernetes/analytics/`
- `app/kubernetes/inventory/` <-> `app/templates/kubernetes/inventory/`
- `app/storage/object_storage/analytics/` <-> `app/templates/storage/object_storage/analytics/`
- `app/integrations/observability/metrics_source/application/` <-> `app/templates/integrations/observability/metrics_source/`
- `app/integrations/observability/alert_source/providers/alertmanager/application/` <-> provider templates below the same integration hierarchy.

Definitions mirror ownership where practical under `app/definitions/catalogs/`: Access definitions under `access/`, Kubernetes definitions under `kubernetes/`, Intelligence definitions under `intelligence/`, and Platform Operations definitions under `platform_operations/`.

## Naming guardrails

Do not create new top-level application packages for individual products. Do not recreate `app/utils/` as a generic junk drawer. Shared code belongs in a specifically named `app/common/<capability>/` module only when more than one bounded context actually owns that contract.

Avoid generic new modules such as `helpers.py`, `misc.py`, or `stuff.py`. Name modules for the responsibility they own.

## Change process

Namespace refactors use hard cutover semantics:

1. move the canonical package;
2. update imports, templates, definitions, tests, Celery references, and verifiers;
3. remove the old namespace;
4. do not add compatibility import wrappers;
5. run architecture, import-symbol, import-cycle, code-health, UI, and contract gates;
6. commit the refactor atomically while the application is runnable.

## Test package mirror

Functional tests mirror application ownership directly: `tests/kubernetes/analytics/`, `tests/storage/object_storage/inventory/`, `tests/platform_operations/jobs/`, and similar domain paths. Purpose buckets (`tests/unit/`, `tests/integration/`, `tests/security/`, `tests/rendering/`, `tests/e2e/`, and `tests/contracts/`) keep the purpose as the first dimension and mirror the same domain tree underneath it. Retired capability-first paths such as `tests/analytics/`, `tests/inventory/`, `tests/dashboards/`, and `tests/kubernetes_operations/` must not be recreated.
