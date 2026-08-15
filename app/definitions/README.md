# KAORI Definition Registry v1.1

System-owned, human-reviewed definitions live as YAML under `app/definitions/catalogs/`.
Application code must load them through domain adapters and validated Python models; routes,
templates, provider adapters, and enforcement code must not parse YAML directly.

Boundary:
- YAML owns declarative definition metadata and ordered policy/check catalogs.
- Python owns validation, evaluators, authorization enforcement, provider calls, transaction boundaries, and resolver execution.
- PostgreSQL/provider APIs own mutable runtime state, assignments, decisions, alerts, journals, and observations.

Every document requires `schema_version: 1` and a canonical `kind`. Duplicate YAML keys,
duplicate canonical identifiers, unknown enum values, and broken cross-references fail closed.


Integration contracts are also source-controlled under `catalogs/integrations/`:
- domain/capability taxonomy and managed consumer-asset metadata,
- generic product/version compatibility profiles and Kubernetes lifecycle policy,
- Kubernetes provider capabilities,
- Prometheus provider capabilities and consumer binding profiles,
- Alertmanager provider capabilities, compatibility profiles, and consumer profiles,
- Object Storage/MinIO API capabilities and qualified release profiles.

Integration adapters retain network validation, query execution, credential handling, and provider-specific algorithms.

Reports definitions are split by authority:
- `catalogs/reports/catalog.yaml` owns executable report types and output-format contracts.
- `catalogs/reports/coverage.yaml` owns planned/reserved report-family coverage shown by Reports Overview and never grants execution eligibility.
