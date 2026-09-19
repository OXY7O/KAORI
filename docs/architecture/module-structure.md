# KAORI module structure standard

This document is the default rule for new and existing KAORI application modules.
Domain README files may add stricter rules, but must not contradict this standard.

## Default dependency direction

```text
route / CLI / Celery task
        -> service.py
        -> domain helpers, queries, adapters, presentation
        -> model or external client
```

Routes, commands, and tasks are delivery boundaries. They validate input, enforce
access, call a service use case, and render a response. Business decisions do not
belong in those files.

## Standard file responsibilities

- `routes.py`: HTTP and HTMX boundary only.
- `service.py`: application use cases, orchestration, and domain rules.
- `queries.py`: reusable read queries, filtering, aggregation, and pagination.
- `writer.py`: optional persistence-only module when write logic is substantial.
- `presentation.py`: conversion into UI, report, or API-ready structures.
- `client.py`: external-system transport adapter.
- `collector.py`: collection and source-data transformation.
- `tasks.py`: Celery entrypoints; call services instead of duplicating logic.
- `constants.py`: stable domain constants, not mutable runtime state.
- `types.py`: domain value objects and typed results.
- `exceptions.py`: domain-specific exceptions translated at boundaries.

Small domains do not need every file. Add a module only when it owns a distinct
responsibility; do not split code merely to create symmetry.

## Service rule

A service is not a re-export facade. It must own a real use case or orchestration
step. Feature modules should depend on another domain's public service API rather
than importing its writer, query, presentation, or private helper modules.

## README rule

Create `app/<domain>/README.md` when at least one condition applies:

- the domain has multiple submodules or subdomains;
- it is a cross-domain platform capability;
- it owns security, retention, background-job, reporting, or integration rules;
- its source-of-truth or dependency boundary is easy to misuse;
- future contributors need explicit extension instructions.

Do not create README files for trivial route-only folders. General rules belong in
`docs/architecture`; domain README files contain only domain-specific decisions.

## Cross-cutting rules

- Use HTMX for KAORI partial updates; avoid parallel frontend state systems.
- Celery tasks must be restart-safe and expose user-friendly progress/failure state.
- Never expose raw stack traces, transport exceptions, SQL errors, or payload dumps
  in notifications or user-facing pages.
- Keep stored identifiers stable. Convert them into human-readable labels in the
  presentation layer.
- Database migrations are required for schema changes; runtime fallbacks must not
  silently conceal missing migrations.
- New files and public use cases must pass Ruff and Python compile checks.

## Reachability and dormant-code rule

Every application module must have at least one concrete consumer:

- an internal application import;
- a configured runtime entrypoint such as a Celery task module;
- a permanent behavior test;
- or an operational script consumer.

Do not pre-create worker, query-planning, repository, adapter, wrapper, or compatibility modules for a future feature. Introduce the module with the first real use case and its behavior tests. `scripts/verify_module_reachability.py` enforces this rule.

## Import initialization rule

Application modules should import extension objects from their owning module, for example:

```python
from app.extensions.db import db
from app.extensions.limiter import limiter
```

Domain code must not import the aggregate `app.extensions` bootstrap package. Aggregate imports are reserved for application startup. This prevents extension initialization from pulling unrelated model, authentication, and notification graphs into ordinary domain imports.

The runtime import graph must remain acyclic. Imports used only for annotations belong under `if TYPE_CHECKING`.

## Size and decomposition rule

The default debt ceilings are recorded in `docs/architecture/code-health-debt-baseline.json`. They are not design targets. New or substantially changed code should normally stay below:

- 800 physical lines per module;
- 160 physical lines per function;
- 30 branch points per function;
- 8 arguments per function.

When a listed legacy module is changed for a new feature, prefer extracting a real application use case, query, presentation, or resource module rather than increasing its exception ceiling.

## UI component rule

Reusable UI behavior belongs in `app/templates/components/` or a static frontend module. Dynamic progress widths must use `components/progress_bar.html`; templates outside that component may not define inline styles. Page-specific scripts and inline event handlers are existing burn-down debt and may not increase.

## Test ownership rule

Permanent behavior tests live in `tests/<domain>/`. Architecture contracts, migration behavior, and temporary diagnostics live in their dedicated folders. A contract test may protect a boundary, but it does not replace a feature test that executes the actual decision, normalization, persistence, or failure behavior.

## Release-candidate debt baseline normalization

After the 2026-08-10 canonical Ruff/djLint formatting pass and completion of the locked pre-release workspace baseline, the code-health debt ledger was re-captured from the formatted source. This is a ledger synchronization, not a relaxation of KAORI's design targets: the default ceilings remain 800 module lines, 160 function lines, 30 branch points, and 8 arguments.

`scripts/verify_code_health_baseline_integrity.py` requires every debt exception to equal the current measured value exactly. The ledger therefore has no growth allowance: any increase fails `verify_code_health.py`, while any reduction requires the resolved or reduced debt to be recorded in the same change. Broad exception handlers remain visible burn-down debt and must not increase.
