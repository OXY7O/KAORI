# KAORI Definition Registry v1

System-owned, human-reviewed definitions live as YAML under `app/definitions/catalogs/`.
Application code must load them through domain adapters and validated Python models; routes,
templates, provider adapters, and enforcement code must not parse YAML directly.

Boundary:
- YAML owns declarative definition metadata and ordered policy/check catalogs.
- Python owns validation, evaluators, authorization enforcement, provider calls, transaction boundaries, and resolver execution.
- PostgreSQL/provider APIs own mutable runtime state, assignments, decisions, alerts, journals, and observations.

Every document requires `schema_version: 1` and a canonical `kind`. Duplicate YAML keys,
duplicate canonical identifiers, unknown enum values, and broken cross-references fail closed.
