# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]

### Added

- Release-governance documentation and an automated release-metadata verifier.

### Changed

- Kubernetes Dashboard Top Consumers now uses KAORI Violet for normal CPU and memory ranking signals.
- Dashboard consumer copy now describes committed snapshot evidence instead of implying direct browser-time Prometheus access.
- Analytics materialization builders are resolved only when worker materialization executes, removing an eager service-registry import cycle.
- TLS certificate job identifiers are owned by the TLS governance constants module instead of the dispatcher implementation.
- Canonical job-operation display labels are shared through a domain-neutral execution presentation contract.

### Fixed

- Added the Analytics compact-label verifier to the canonical static quality gate.
- Removed runtime import cycles in Analytics, TLS Governance, and the Prometheus query-profile package.
- Restored the shared Reports recent-report serializer and explicit Reports schedules package boundary required by internal import validation.

### Removed

- Unreachable `app/users/identity.py`; authentication provider-family ownership remains canonical in `app/auth/providers/catalog.py`.
- Dormant `app/knowledge/remediation_workflow.py`; Intelligence remediation remains held for the next controlled redesign.

### Security

- Removed the dormant end-to-end remediation orchestrator from the current release source while Intelligence remediation is held for the next controlled redesign.

## [2.1.0]

Structured changelog tracking starts after the 2.1.0 baseline. Earlier implementation history remains available in Git history and the historical review/audit documents under `docs/`.
