# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]

### Changed
- Added Rule Catalog Accepted Risk / Rule Exception governance with mandatory expiry, owner/audit evidence, asset-wide or selected-finding scope, and revocation.
- Added grouped recommendation-to-alert promotion for Object Storage bucket encryption findings so one rule/asset AlertCase can represent many affected buckets while preserving child finding evidence.
- Added accepted-risk lifecycle handling so covered findings remain visible as non-compliant evidence, are suppressed from AlertCase promotion while the exception is active, and automatically return to normal eligibility after expiry or revocation.
- Finalized KAORI Intelligence UI hierarchy across Recommendations, Alert Operations, Rule Catalog, and Automation Control.
- Stabilized Alert Operations loading scope, resolved-case closure workflow, notification routing, and Telegram alert presentation.
- Completed Intelligence typography, contract, Ruff, and djLint quality cleanup for release readiness.
- Simplified Rule Catalog table summaries using compact sentence-level summaries.
- Added section spacing between stacked registry tables in Automation Control workspaces.
- Redesigned Binding Configuration, Execution Configuration, and Record Readiness Evidence modals with clearer section hierarchy while preserving governance boundaries.

### Security
- Accepted-risk exceptions are durable, time-bounded, permission-gated, owner/audit-backed governance records; they never rewrite source truth or claim technical recovery.
- Added the `rule_exceptions` migration and recommendation-state exception linkage while preserving default-deny execution boundaries.

## [2.3.0] - 2026-08-18

### Changed
- Published the KAORI 2.3.0 release baseline. Full release scope and verification evidence are recorded in `docs/releases/KAORI_2_3_0.md`.

## [2.2.0] - 2026-08-11

### Changed
- Previous release baseline; detailed implementation history remains available in Git history and archived release documentation.
