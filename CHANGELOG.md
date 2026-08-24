# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]

### Changed
- Standardized Kubernetes and Object Storage operational dashboards as the KAORI dashboard-family reference, including aligned layout, concise operational copy, and a governed Reporting Control block.
- Refined Intelligence work-inbox, accepted-risk, Rule Catalog, and posture-summary presentation while preserving the canonical evidence and governance boundaries.
- Simplified Object Storage Analytics PDF output into a management-oriented overview and strengthened analytics PDF readability/canvas-safety rules.
- Finalized KAORI Intelligence UI hierarchy across Recommendations, Alert Operations, Rule Catalog, and Automation Control.
- Stabilized Alert Operations loading scope, resolved-case closure workflow, notification routing, and Telegram alert presentation.
- Completed Intelligence typography, contract, Ruff, and djLint quality cleanup for release readiness.
- Simplified Rule Catalog table summaries using compact sentence-level summaries.
- Added section spacing between stacked registry tables in Automation Control workspaces.
- Redesigned Binding Configuration, Execution Configuration, and Record Readiness Evidence modals with clearer section hierarchy while preserving governance boundaries.

### Fixed
- Aligned dashboard, Notification Deck, Automation Control, and release-gate verifiers with the current canonical UI contracts.
- Cleaned remaining Ruff and djLint formatting drift discovered by the final release gate.

### Security
- No migration, route-name, form-field, or execution-gate ownership changes are introduced by the Intelligence UI cleanup.

## [2.3.0] - 2026-08-18

### Changed
- Published the KAORI 2.3.0 release baseline. Full release scope and verification evidence are recorded in `docs/releases/KAORI_2_3_0.md`.

## [2.2.0] - 2026-08-11

### Changed
- Previous release baseline; detailed implementation history remains available in Git history and archived release documentation.
