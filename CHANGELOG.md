# Changelog
- Centralized observability binding mutation on Prometheus/Alertmanager source workspaces, made Kubernetes/MinIO lifecycle binding views read-only, generalized eligible consumer assets through a shared registry for future providers such as Vault, and standardized capability/readiness/configuration surfaces across Integration details.
- Corrected domain binding semantics and interaction ownership: Storage/Orchestration now expose only consumer bindings (Prometheus/Alertmanager), provider workspace actions remain visible in empty and populated states, Provider Registry/Bindings switch through HTMX without full-page reload, and MinIO owner self-bindings are retired with data cleanup.
- Aligned MinIO with Kubernetes asset-owner lifecycle semantics: reusable configuration/edit flow, Core Validation, manual Runtime Refresh, governed Prometheus/Alertmanager consumer bindings, guarded Delete Connection, and retained shared observability sources/history.
- Unified provider registration action footers on one embedded gate-state component: Test Connection readiness now renders as a compact status surface, Cancel/Register actions share one responsive geometry, and verified state enables the canonical primary CTA across Kubernetes, Prometheus, Alertmanager, and MinIO.
- Standardized provider registration field labels, placeholders, Cancel actions, and helper-text density across Kubernetes, Prometheus, Alertmanager, and MinIO; hardened MinIO connection-test diagnostics and separated S3 reachability from product-identity Core Validation.
- Simplified provider connection right rails to one shared Flow + Related Operational Workspace contract and fixed Kubernetes front-page typing/overview regressions detected by Pyright.
- Unified Kubernetes, Prometheus, Alertmanager, and MinIO registration Heroes on one reusable contract; Kubernetes now uses `Register Kubernetes Connection`, the same Draft/Pre-save posture panel, and the same Test Connection → Core Validation progression as the other providers.

- Standardized provider empty states and registration UX: consumer coverage now uses asset terminology, route-owned authorization avoids redundant `Admin Required` states, and MinIO Test Connection follows the same operation-scoped HTMX proof flow as Kubernetes, Prometheus, and Alertmanager.

- Refactored Integration provider front pages to share one DRY Hero, Integration Overview, canonical Connection Registry column contract, and reusable direct/observability coverage table geometry across Kubernetes, Prometheus, Alertmanager, and MinIO.
- Unified Kubernetes, Prometheus, Alertmanager, and MinIO provider landing pages on one canonical front-page hierarchy: Operational Integration Hero, shared Integration Overview, Integration Coverage, and Connection Registry; MinIO empty states now retain the same filter/table/pagination geometry as populated states.
- Fixed Integration binding success-path type narrowing so Pyright no longer treats the resolved Kubernetes asset as optional after a successful binding create.
- Cleaned active Alertmanager workspace djLint findings (T002/H037) and aligned capability pagination URL construction with the Prometheus registry pattern.

- Refined Integration domain workspace UX across Orchestration, Observability, and Storage: separated tab rails from registry table surfaces, preserved readable row text with the sidebar open, normalized operator-facing Prometheus naming, isolated operation-specific loading bars, and added live HTMX tab-status refresh for validation/runtime updates.
- Refined Integration domain landing-page UX by removing duplicated KPI tiles, using compact capability/provider metadata, and replacing empty provider metrics with an explicit registration-validation-binding onboarding path.

All notable KAORI changes are recorded here. KAORI uses Semantic Versioning for release identity.

## [Unreleased]

### Fixed
- Aligned Prometheus Integration contract assertions with canonical djLint double-quote Jinja tags and Ruff-formatted the consumer-profile verifier so quality gates no longer fail on formatting-only drift.
- Normalized the MinIO provider detail template to the canonical djLint format so the global template-format gate no longer stops on `app/templates/minio/instance_detail.html`.
- Repaired Integration domain route ownership so Flask application boot and `flask db upgrade` import `build_integration_domain_page` directly from `domain_service` instead of a removed `service.py` re-export.

### Changed
- Centralized Prometheus/Alertmanager consumer binding mutation in Observability, introduced the canonical consumer-asset registry (`kubernetes_cluster`, `object_storage_system`, future extensible assets), made Kubernetes/MinIO `Inventory & Lifecycle` binding evidence read-only, and standardized capability/readiness/Operational Context presentation across provider details.
- Domain Integration Bindings now represent only consumer-source relationships; native asset-owner attachments are excluded from binding counts and UI, domain tabs use HTMX replacement with persistent provider workspace actions, and legacy MinIO self-bindings are removed by migration.
- Aligned MinIO provider details with the Kubernetes asset-owner lifecycle: `object_storage_system` configuration is editable without recreating consumer bindings, runtime health refresh is operation-scoped, and `Inventory & Lifecycle` shows bound observability sources read-only plus guarded deletion while binding mutation stays in Prometheus/Alertmanager.
- Unified provider registration action footers on one embedded gate-state component: Test Connection readiness now renders as a compact status surface, Cancel/Register actions share one responsive geometry, and verified state enables the canonical primary CTA across Kubernetes, Prometheus, Alertmanager, and MinIO.
- Standardized provider front pages across Kubernetes, Prometheus, Alertmanager, and MinIO with shared overview geometry and framed Coverage/Registry tabs while preserving provider-specific evidence inside those tabs.
- Generalized Alertmanager around consumer-neutral Core Validation and asset-scoped alert Consumer Profiles, including `kubernetes-alerts-v1` and `minio-alerts-v1`, so shared Alertmanager instances can segregate Kubernetes, MinIO, and future alert streams by binding selector without false provider degradation.
- Aligned MinIO provider pages with the canonical Integration workspace: `MinIO Integrations` + `Register Connection`, Integration Coverage/Connection Registry, shared registration workflow, and Configuration/Validation & Capabilities/Runtime & History/Inventory & Lifecycle detail tabs.
- Unified Orchestration, Observability, and Storage domain landing pages on one Capability Registry + Provider Registry + Bindings workspace, including asset-owned cross-domain binding visibility and canonical five-row pagination.
- Locked the canonical Integration lifecycle in architecture/workspace documentation: Provider → Compatibility Profile → Provider Capability Set → Core Validation → Binding → Consumer Profile → Binding Validation → Consumer Eligibility.
- Generalized Prometheus provider readiness around the consumer-neutral `prometheus-core-v1` contract and moved Kubernetes/MinIO metric, label, PromQL, and capability evidence to asset-scoped `IntegrationBinding` consumer profiles.
- Added `kubernetes-metrics-v1` and `minio-metrics-2024-v1` binding profiles plus persisted binding validation profile/evidence so one Prometheus source can serve multiple managed-asset types without false provider degradation.

## [2.2.0] - 2026-08-11

### Added
- Added a release-test prerequisite preflight that verifies required development test dependencies and unique pytest module basenames before the full suite starts.
- Added a canonical 49-link / 21-blueprint release-surface registry, concise general final-release runner, static ownership verifier, and runtime endpoint-registry integration test so new menus/domains cannot bypass release ownership.
- Added permanent Kubernetes Governance L0–L7 release evidence and `verify_governance_final_lock.py` for AuthZ-first readiness, TLS data minimization, canonical UI ownership, and dead-surface protection.
- Added permanent Kubernetes Inventory L0–L7 release evidence and `verify_inventory_final_lock.py` for AuthZ ordering, committed-snapshot ownership, canonical UI composition, Topology database ownership, and residual-file protection.
- Established `docs/standards/KAORI_ENGINEERING_STANDARD_V1.md` as the mandatory final-recheck index covering the shared Violet palette, Hero variants, tables/pagination/status, right context rails, tab families, progressive disclosure, feedback, notifications, shell navigation, accessibility, security, and test evidence.
- Added permanent Welcome behavioral characterization and direct Welcome final-lock gate coverage for the final release recheck.
- Release-governance documentation and an automated release-metadata verifier.
- Pre-release type-safety guardrails for provider exceptions, Secret scrubbing, snapshot boundaries, recovery counters, ORM construction, and XLSX page setup.

### Changed
- Baseline-lock Intelligence read/evidence surfaces while preserving explicit Reserved Plan and fail-closed boundaries for unfinished Server/HCI and Automation Control capabilities; environment enablement for Automation mutations remains deliberately deferred.
- Standardized the general release console on short `PASS — KAORI <Area>` titles while preserving complete captured diagnostics on failed child verifiers; full static/test/frontend phases remain delegated to the canonical quality gate.
- Closed the remaining Reports UI style/reuse gate debt by centralizing semantic borders, PDF dynamic fill styling, generated/template progress ownership, and Schedule form runtime while preserving the locked Reports presentation and delivery contracts.
- Final-locked Settings across General Settings and Account & Authentication, retiring obsolete side-context partials and standardizing active preference/credential surfaces on shared KAORI semantic UI ownership.
- Final-locked the Access control plane across Overview, User Management, Identity Providers, Roles & Access, Permission Catalog, and Activity Audit with a permanent release verifier and canonical short PASS output.
- Standardized reviewed final-lock verifier success output to compact `PASS — KAORI …` lines while retaining detailed failure diagnostics and coverage assertions.
- Hardened Kubernetes Analytics final-recheck contracts: shared Content Tabs now own visual state tokens, materialized snapshot identity has a dependency-light owner, canonical snapshot decode is ORM-free, Forecast reprojection builds only current payload fields, and explicit L0–L7 release evidence is registered.
- Fixed Protected Reveal tabs so each peer workspace retains a server-navigation fallback while client-side switching remains progressively enhanced.
- Standardized ConfigMap/Secret CRUD target-field vertical alignment through a shared form-field primitive, restored Secret Replace actions inside the HTMX-refreshed target content, and repaired the Design System final-recheck Engineering Standard index.
- Standardized reviewed Kubernetes Operations task pages on the shared **Form + Right Context** pattern: ConfigMap Create/Update/Delete, Secret Create/Replace/Delete, and Protected Reveal `New Request` now reuse one 8/12 main-task + 4/12 contextual-guidance geometry derived from the proven Integration registration forms. TLS workflows and Reveal registries retain their dedicated reviewed layouts.
- Corrected Kubernetes Operations functional release wiring and test harness assumptions: the nonexistent `tests/kubernetes` path was removed, clusterless onboarding expectations now respect RBAC, standalone Secret template rendering provides CSRF context, Secret create tests isolate TLS policy resolution, and TLS persistence failure tests now emulate `SQLAlchemyError`.
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
- Removed the orphan standalone Cluster Management listing template chain and stale `can_clusters` sidebar capability; active Cluster Add/Edit/Delete/Sync operations remain nested under Integrations → Kubernetes.
- Removed retired Settings side-context partials for General preference impact, Account profile information, and authentication activity information; canonical evidence remains inline in the active locked workspaces.
- Retired the Analytics compatibility Content Tabs wrapper, orphan snapshot/freshness templates, and the unused Alerts Alpine-tab rehydration bridge; current pages consume canonical shared components directly.
- Removed the orphan TLS Governance `get_active_tls_sync_job()` presentation helper; no compatibility wrapper is retained.
- Removed unused Inventory `format_byte_count`, `format_gib`, and `_split_inventory_values` helpers plus the stale empty Inventory partial README; no compatibility wrapper is retained.

### Fixed
- Hardened functional-test module isolation so temporary `sys.modules` stubs are restore-safe and cannot corrupt later Flask application characterization tests.
- Aligned Analytics runtime characterization with the canonical dependency-failure envelope, Storage capability evidence, and absolute-versus-percent Top Consumer semantics.
- Restored release code-health line budgets without increasing debt ceilings and made failed general release phases suppress unrelated success chatter.
- Fixed full release-test collection by declaring `pypdf` as a development-only dependency and removing the duplicate `test_operation_flow.py` module basename collision.
- Normalized Kubernetes Analytics final-recheck contracts around semantic behavior instead of quote/whitespace fingerprints while preserving Watch posture, shared semantic tone ownership, null-safe Forecast thresholds, Prometheus timestamp fallback, Storage pressure fallbacks, Utilization legend roles, and Workload View More boundaries.
- Made the Integrations latest-runtime-observation contract formatter-neutral by validating the ranked database query semantically within its owning function instead of matching one exact call layout.
- Fixed Kubernetes Analytics tabs that could remain inert or visually desynchronized by removing dual Alpine/native state ownership; Overview now uses compact one-row labels and no longer renders internal snapshot identifiers as badges.
- Harden Protected Secret Reveal cleanup by restoring shared Secret payload scrubbing imports, make form-field contracts formatter-neutral, and normalize Reveal templates against the canonical Ruff/djLint output.
- Fixed Protected Reveal one-time consumption on PostgreSQL by suppressing joined eager relationships on the locking query and locking only the `secret_reveal_requests` row; aligned the My Requests step-up password and Verify Session action on the shared form-field baseline.
- Stabilized Protected Secret Reveal refresh/tab ownership so the server-rendered active panel remains authoritative until the client validates a complete tab/panel pair; URL view state now outranks stale hash anchors, and the Platform Operations lock follows the current Form + Right Context contract instead of the retired generic context rail.
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
- Restored Access security invariants: failed authentication targets no longer count as authenticated actors, remember-me persistence is bounded to a 7-day default within 1–30 days, and the shared content-driven modal keeps its Tailwind viewport-height token formatter-safe.
- Analytics refresh-failure surfaces now render parsed operator-safe detail/remediation fields instead of the raw stored worker error string.
- Closed a Kubernetes Operations authorization-order regression by retiring the Blueprint clusterless `before_request`; ConfigMap, Secret, Protected Reveal, and TLS cluster prerequisites now execute only after route RBAC.
- Closed a Governance authorization-order regression where Blueprint-level clusterless handling could respond before `tls_certificates.view` / `tls_certificates.sync`; readiness now runs only inside authorized TLS request paths.
- Closed an Inventory authorization-order regression where Blueprint-level clusterless HTMX handling could respond before route-level `inventory.view`; readiness evaluation now occurs only after authorization.
- Narrowed 21 database, credential-decoding, and report-catalog exception boundaries to explicit exception classes; the broad-exception burn-down ceiling remains 198 rather than increasing with the stale ledger.
- Removed the dormant end-to-end remediation orchestrator from the current release source while Intelligence remediation is held for the next controlled redesign.

## [2.1.0]

Structured changelog tracking starts after the 2.1.0 baseline. Earlier implementation history remains available in Git history and the historical review/audit documents under `docs/`.

- Align Integration detail configuration and coverage semantics: Prometheus/Alertmanager Configuration tabs are now read-only contracts with dedicated Edit Connection routes, all provider detail Hero posture panels share one geometry, edit right rails keep only Flow + Related Operational Workspace, and Observability coverage includes both Kubernetes and MinIO-managed object-storage assets.
