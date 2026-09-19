# KAORI Definition Registry v1.1

KAORI separates system-owned definitions from runtime state and executable code.

## Flow

`YAML definition -> strict loader -> domain validation/model -> service/evaluator -> presentation`

Templates, routes, provider adapters, and workers must never parse definition YAML directly.

## YAML-owned

- Intelligence Rule Catalog metadata and evidence contracts.
- RBAC permissions and built-in system-role grants.
- System Runbook Catalog definitions.
- Automation production-readiness check/stage catalog.
- Authentication provider metadata.
- Registered background-job metadata and callable references.
- Kubernetes Analytics materialization dataset metadata.
- Report type and output-format catalog.
- Evidence-ready, planned, and reserved report coverage domains used by Reports Overview.
- Notification Center category/routing metadata.
- Integration domain/capability taxonomy and managed consumer-asset metadata.
- Kubernetes, Metrics Source, Alertmanager, and Object Storage provider capability catalogs.
- Annual integration lifecycle policy, general capability-contract profiles, and product/version qualification mappings.
- Provider-local non-semver qualification evidence, including the MinIO date-release lifecycle mapping.
- Metrics Source and Alertmanager consumer binding/validation profiles.

## Code/DB-owned

- Rule evaluators and alert/provider queries.
- RBAC authorization enforcement and user/custom-role assignments.
- Resolver implementations, dry-run, execution, verification and recovery enforcement.
- Decision candidates, immutable decisions, approvals, execution authorization and journals.
- Provider alert state, silences, inhibition and routing state.
- Provider network probes, validation algorithms, query execution, credentials, and runtime health.
- Job executions/policies, report records, analytics snapshots and inventory snapshots.
- Transaction boundaries, security guardrails and secret handling.

## Safety rules

Every definition file has `schema_version: 1` and a canonical `kind`. YAML is loaded with a duplicate-key rejecting safe loader. Domain adapters reject duplicate identifiers, unknown enum values and broken references. Compatibility validation additionally checks annual-policy arithmetic, support-posture references, contract-to-product ownership, qualification-to-contract mappings, and provider-local alignment. CI runs `scripts/verify_definition_registry.py` before the rest of the release gates.

The registry is fail-closed: invalid system definitions prevent the affected module from initializing rather than silently falling back to a different policy.
