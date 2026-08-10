# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]

### Added

- Added permanent Welcome behavioral characterization and direct Welcome final-lock gate coverage for the final release recheck.
- Release-governance documentation and an automated release-metadata verifier.
- Pre-release type-safety guardrails for provider exceptions, Secret scrubbing, snapshot boundaries, recovery counters, ORM construction, and XLSX page setup.

### Changed

- Synchronized the code-health debt ledger with the canonical formatted release-candidate source while keeping the 800/160/30/8 default ceilings unchanged, and added an integrity verifier that forbids hidden slack or stale debt entries.

- Normalized Python and Jinja sources to the canonical Ruff and djLint formatting contracts used by the release quality gate.
- Modernized typed dictionaries, generic declarations, type aliases, collection ABC imports, and response annotations for the Python 3.12+ baseline.
- Kubernetes Dashboard Top Consumers now uses KAORI Violet for normal CPU and memory ranking signals.
- Dashboard consumer copy now describes committed snapshot evidence instead of implying direct browser-time Prometheus access.
- Analytics materialization builders are resolved only when worker materialization executes, removing an eager service-registry import cycle.
- TLS certificate job identifiers are owned by the TLS governance constants module instead of the dispatcher implementation.
- Canonical job-operation display labels are shared through a domain-neutral execution presentation contract.

### Fixed

- Completed the follow-up quality-gate cleanup from the second lint/type run: restored required workload quota bindings, fixed forecast snapshot recommendation counting, corrected Kubernetes Operations contract setup, widened the cluster dependency typing boundary for SQLAlchemy models, and added optional-value guards for forecast PDF, XLSX footer, dashboard pagination, and scheduled report dispatch paths.
- Resolved pre-release lint and type-safety defects across Analytics, Inventory, Governance, Kubernetes Operations, Reports, Integrations, Platform Operations, Access support code, and release scripts.
- Restored required Prometheus exception and Secret scrubber imports, eliminating two runtime-name failures detected by the quality gate.
- Aligned formatter-sensitive lock verifiers with semantic module, symbol, tab-order, and loading-indicator contracts instead of whitespace-specific assertions.
- Restored the Reports Storage S3 connectivity banner with sanitized operator guidance and an explicit retry action when artifact storage is unreachable.
- Added the Analytics compact-label verifier to the canonical static quality gate.
- Removed runtime import cycles in Analytics, TLS Governance, and the Prometheus query-profile package.
- Removed unreachable current-release modules that had no runtime, test, script, or configured entrypoint consumer.

### Security

- Narrowed 21 database, credential-decoding, and report-catalog exception boundaries to explicit exception classes; the broad-exception burn-down ceiling remains 198 rather than increasing with the stale ledger.
- Removed the dormant end-to-end remediation orchestrator from the current release source while Intelligence remediation is held for the next controlled redesign.

## [2.1.0]

Structured changelog tracking starts after the 2.1.0 baseline. Earlier implementation history remains available in Git history and the historical review/audit documents under `docs/`.
