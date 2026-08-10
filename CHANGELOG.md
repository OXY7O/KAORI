# Changelog

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]
### Added

- Added permanent Kubernetes Governance L0–L7 release evidence and `verify_governance_final_lock.py` for AuthZ-first readiness, TLS data minimization, canonical UI ownership, and dead-surface protection.
- Added permanent Kubernetes Inventory L0–L7 release evidence and `verify_inventory_final_lock.py` for AuthZ ordering, committed-snapshot ownership, canonical UI composition, Topology database ownership, and residual-file protection.
- Established `docs/standards/KAORI_ENGINEERING_STANDARD_V1.md` as the mandatory final-recheck index covering the shared Violet palette, Hero variants, tables/pagination/status, right context rails, tab families, progressive disclosure, feedback, notifications, shell navigation, accessibility, security, and test evidence.
- Added permanent Welcome behavioral characterization and direct Welcome final-lock gate coverage for the final release recheck.
- Release-governance documentation and an automated release-metadata verifier.
- Pre-release type-safety guardrails for provider exceptions, Secret scrubbing, snapshot boundaries, recovery counters, ORM construction, and XLSX page setup.

### Changed

- Rebuilt Kubernetes Operations ConfigMap/Secret mutation workspaces as **Full-Width Mutation Workspace v2**, replacing the retired content right rail with bounded target/payload/impact sections plus shared workflow, guardrail, and embedded-action controls.
- Rebuilt TLS Certificate Detail into the compact `evidence-workspace-v2` composition, grouping identity/validity, coverage/consumers, and collection/Governance evidence instead of nested detail-card stacks.
- Refined `Target TLS Secret` into a three-column identity strip plus compact posture metrics and a dedicated Issuer/Fingerprint row, retiring the space-heavy target/posture split.
- Hardened Kubernetes Governance request ownership so TLS cluster/readiness blockers execute only after route RBAC, while preserving the locked TLS registry, worker sync, operational feedback, and rotation handoff design.
- Hardened Kubernetes Inventory read ownership: clusterless HTMX blocking now executes after `inventory.view`, and Topology reads API Server metadata from the eagerly loaded canonical cluster-connection relationship instead of the integration resolver.
- Harden Kubernetes Dashboard release ownership: remove unused compatibility/dead internal surface, use explicit selected-cluster naming, keep empty consumer messaging snapshot-only, and add layered Unit/Integration/Security/Rendering/E2E release evidence without changing the locked visual design.
- Restarted the final release recheck from Welcome under the consolidated KAORI Engineering Standard v1 and recorded the per-standard applicability matrix for locked-page review.
- Synchronized the code-health debt ledger with the canonical formatted release-candidate source while keeping the 800/160/30/8 default ceilings unchanged, and added an integrity verifier that forbids hidden slack or stale debt entries.

- Normalized Python and Jinja sources to the canonical Ruff and djLint formatting contracts used by the release quality gate.
- Modernized typed dictionaries, generic declarations, type aliases, collection ABC imports, and response annotations for the Python 3.12+ baseline.
- Kubernetes Dashboard Top Consumers now uses KAORI Violet for normal CPU and memory ranking signals.
- Dashboard consumer copy now describes committed snapshot evidence instead of implying direct browser-time Prometheus access.
- Analytics materialization builders are resolved only when worker materialization executes, removing an eager service-registry import cycle.
- TLS certificate job identifiers are owned by the TLS governance constants module instead of the dispatcher implementation.
- Canonical job-operation display labels are shared through a domain-neutral execution presentation contract.

### Removed

- Removed the orphan TLS Governance `get_active_tls_sync_job()` presentation helper; no compatibility wrapper is retained.
- Removed unused Inventory `format_byte_count`, `format_gib`, and `_split_inventory_values` helpers plus the stale empty Inventory partial README; no compatibility wrapper is retained.

### Fixed

- Restored authenticated top-navbar Quick Actions, Notification Deck, and Account interactions by moving the malformed inline Alpine state program into the syntax-checked `kaoriNavbar` static controller.
- Completed the follow-up quality-gate cleanup from the second lint/type run: restored required workload quota bindings, fixed forecast snapshot recommendation counting, corrected Kubernetes Operations contract setup, widened the cluster dependency typing boundary for SQLAlchemy models, and added optional-value guards for forecast PDF, XLSX footer, dashboard pagination, and scheduled report dispatch paths.
- Resolved pre-release lint and type-safety defects across Analytics, Inventory, Governance, Kubernetes Operations, Reports, Integrations, Platform Operations, Access support code, and release scripts.
- Restored required Prometheus exception and Secret scrubber imports, eliminating two runtime-name failures detected by the quality gate.
- Aligned formatter-sensitive lock verifiers with semantic module, symbol, tab-order, and loading-indicator contracts instead of whitespace-specific assertions.
- Restored the Reports Storage S3 connectivity banner with sanitized operator guidance and an explicit retry action when artifact storage is unreachable.
- Added the Analytics compact-label verifier to the canonical static quality gate.
- Removed runtime import cycles in Analytics, TLS Governance, and the Prometheus query-profile package.
- Removed unreachable current-release modules that had no runtime, test, script, or configured entrypoint consumer.

### Security

- Closed a Kubernetes Operations authorization-order regression by retiring the Blueprint clusterless `before_request`; ConfigMap, Secret, Protected Reveal, and TLS cluster prerequisites now execute only after route RBAC.
- Closed a Governance authorization-order regression where Blueprint-level clusterless handling could respond before `tls_certificates.view` / `tls_certificates.sync`; readiness now runs only inside authorized TLS request paths.
- Closed an Inventory authorization-order regression where Blueprint-level clusterless HTMX handling could respond before route-level `inventory.view`; readiness evaluation now occurs only after authorization.
- Narrowed 21 database, credential-decoding, and report-catalog exception boundaries to explicit exception classes; the broad-exception burn-down ceiling remains 198 rather than increasing with the stale ledger.
- Removed the dormant end-to-end remediation orchestrator from the current release source while Intelligence remediation is held for the next controlled redesign.

## [2.1.0]

Structured changelog tracking starts after the 2.1.0 baseline. Earlier implementation history remains available in Git history and the historical review/audit documents under `docs/`.
