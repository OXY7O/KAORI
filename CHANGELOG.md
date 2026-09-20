# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for stable release identity.

## [Unreleased]

### Added
- Added standalone Docker Compose integration examples for Prometheus, Alertmanager, MinIO/S3-compatible storage, Thanos Query, and a disposable GitHub Actions Runner under `example/`.
- Added an application-only runtime archive builder and explicit runtime artifact boundary.
- Added repository `LICENSE` and `SECURITY.md` surfaces for current internal-use distribution and private vulnerability reporting.
- Added a canonical KAORI terminal/output readability standard.

### Changed
- Aligned Node.js 22.23.2, npm 10.9.9, and Pyright 1.1.414 across development, CI, and frontend build authorities; documented deferred npm 12 and output-sensitive frontend patch updates.
- Professionalized the KAORI repository front with the canonical logo, restrained badges, clearer product/release/security navigation, and a standalone integration-example entry point.
- Clarified release-version authority: stable SemVer is bound to the governed release workflow, Git tag, GitHub Release, Docker Hub tag, OCI labels, source lineage, and immutable digest rather than development example defaults.
- Established root `VERSION` as the current product version line synchronized with the README badge and development fallback while exact RC/stable `APP_VERSION` remains deployment-managed.
- Standardized Kubernetes and Object Storage operational dashboards as the KAORI dashboard-family reference, including aligned layout, concise operational copy, and a governed Reporting Control block.
- Refined Intelligence work-inbox, accepted-risk, Rule Catalog, and posture-summary presentation while preserving canonical evidence and governance boundaries.
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
- Tightened HTML CSP/site-isolation headers and documented evidence-backed ZAP DAST warning dispositions without weakening the baseline failure gate.
- Removed Bandit suppression parser noise and refreshed the reviewed Semgrep CI toolchain while preserving existing SAST rules and severity gates.
- Demo/example configuration excludes real KAORI Host values, private keys, production credentials, and private integration secrets.
- Runtime artifacts explicitly exclude demo, CI, test, documentation, and local-development surfaces.
- No migration, route-name, form-field, or execution-gate ownership changes are introduced by the repository-hardening work.

## Historical Release Records

Historical `2.x` release documents remain retained for traceability. Current stable public release authority is the governed SemVer tag/GitHub Release/OCI lineage documented in `docs/releases/README.md`.

## [2.3.0] - 2026-08-18

### Changed
- Published the KAORI 2.3.0 historical baseline. Detailed evidence remains in `docs/releases/KAORI_2_3_0.md`.

## [2.2.0] - 2026-08-11

### Changed
- Previous historical baseline; detailed implementation history remains available in Git history and archived release documentation.
