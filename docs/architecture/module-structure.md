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
