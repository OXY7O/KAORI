# Intelligence domain

Intelligence is KAORI's central rule, recommendation, alert-enrichment, and
immutable decision domain. Analytics workspaces consume this domain instead of
maintaining duplicate page-specific recommendation logic.

## Responsibilities

- `catalog.py`: canonical rule definitions and P1-P4 severity semantics.
- `recommendation_engine.py`: rule evaluation and recommendation construction.
- `service.py`: public use cases, filtering, and recommendation orchestration.
- `workflow.py`: immutable decision approval and rejection transitions.
- `routes.py`: read-only domain-owned HTTP/HTMX surfaces for Recommendations and Rule Catalog.
- `../alert_intelligence/`: multi-domain active-alert normalization, scoped recommendation context, and provider-authority presentation.
- `../notification_channels/`: platform-wide outbound delivery integration consumed by Alert Intelligence, Reports, and future governed capabilities.
- `../alert_delivery/`: Alert Intelligence background dispatch orchestration over configured Notification Channels.

Rules must identify source, domain, impacted assets, evidence, and remediation.
Imported and internal rules share one catalog contract. Do not embed page-specific
recommendation rules directly in analytics routes or templates.

## Cross-domain automation orchestration

The **Automation Control Center** is intentionally owned by the application layer
under `app/intelligence/automation_control/`, not by this domain. It coordinates read models
and governed commands across Knowledge, Intelligence, Resolver, and Production
Readiness without making those domains import one another. The application layer
may call Intelligence public use cases; Intelligence must not import the
Automation Control package.

Route: `/intelligence/automation-control`

See `docs/architecture/domain-20-automation-control-center-ui.md`.

## KAORI Violet presentation standard

All Intelligence workspaces use the KAORI Violet Infrastructure design system.
Intelligence Overview, Recommendations, Catalog, Alert Intelligence, and the cross-domain Automation
Control Center share a solid violet hero, a right-side posture card, tokenized
surfaces and borders, `rounded-xl` sections, `rounded-lg` internal object blocks,
violet focus states, and compact rectangular status/metadata labels. Semantic
green, amber, red, cyan, and slate remain reserved for operational state,
priority, or risk; decorative blue gradients and literal slate surfaces must not
be reintroduced.

## Intelligence Workspace Presentation

The category root `/intelligence/` renders **Intelligence Overview**. The landing page is intentionally provider-free: it summarizes committed findings, registered asset coverage, Rule Catalog posture, and Automation Control governance state, while live provider alert retrieval remains owned by Alert Intelligence.

Intelligence Overview, Recommendations, Rule Catalog, Alert Intelligence, and Automation Control use the canonical Intelligence workspace contract documented in `docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md`.

Automation Control is the governed bridge from Intelligence evidence to controlled execution. Its UI exposes factual **Governance Only** state across Overview, Runbooks & Bindings, Decision Review, Execution Control, and Production Readiness whenever infrastructure execution is disabled. Runbooks now use a source-controlled **System Runbook Catalog**: operators activate validated immutable contracts and configure environment-specific bindings instead of authoring action JSON manually. Catalog activation validates adapters shipped by the build without requiring `RESOLVER_ENABLED_ACTIONS`, so Governance Only preparation does not open the runtime execution registry. Custom authoring remains locked behind `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false` until simulation, maturity, regression, and security contracts are production-ready. Deployment policy, safety controls, readiness evidence, and rollout stages remain writable without opening the resolver boundary. Active alert evidence is independently materialized into deduplicated candidates; accountable review uses immutable decisions and maker-checker approval where required. Infrastructure execution is default-deny behind `AUTOMATION_EXECUTION_ENABLED=false` and is revalidated at authorization, application admission, and worker admission. The Kubernetes Deployment restart pilot uses one-time authorization, canonical jobs, server-side dry-run, rollout-health verification, recovery evidence, lifecycle notifications, audit evidence, and immutable dead letters that require fresh evidence for another attempt.

## Intelligence baseline lock v1

The current Intelligence surface is **baseline-locked**, not declared feature-complete.
The lock protects the implemented evidence/read paths and the fail-closed boundary for
capabilities that are still being built. It must not be interpreted as approval to enable
reserved mutations or unfinished provider paths.

Locked current-state contracts:

- **Recommendations** is an active, read-only, multi-domain evidence review surface backed by the
  central Intelligence evaluator. Kubernetes findings remain cluster-scoped for Kubernetes consumers;
  Object Storage findings are evaluated from committed provider-neutral inventory, with MinIO as the
  first validated Object Storage provider. Current forecast recommendations also consume current worker-materialized Object Storage forecast snapshots.
- **Rule Catalog** exposes canonical definitions. Rules that do not yet have a validated
  provider/evaluator path remain **Reserved Plan**.
- **Alert Intelligence** is active for Kubernetes and Object Storage. Automatic alert-source selection prefers Alertmanager and falls back to metric-derived alert-state evidence from the selected Metrics Source adapter; committed Recommendations and Rule Catalog definitions provide contextual enrichment without asserting causal correlation. A global Alert Intelligence Summary remains visible while one tabbed workspace uses the shared KAORI Content Tabs (server-owned link mode) for Alert Records, Correlation & Guidance, Notification Delivery, and Evidence & Ownership. Tabs appear before a compact shared Operational Context (domain/asset/source), while Alert Records owns its own auto-refreshing search/severity/state filters and Reset Filters action with no Apply button. Active section content stays inside the same workspace surface. Server and HCI enrichment remain **Reserved Plan**.
- **Notification Channels** is owned by Integrations, not Intelligence. Alert Intelligence consumes the platform delivery contract while Alertmanager remains the raw alert routing/receiver authority.
- **Automation Control** is an application-layer orchestration surface. Validated System Runbook activation, deterministic environment bindings, candidate review, decision approval/rejection, deployment-policy configuration, safety controls, readiness evidence, and ordered rollout configuration are governance operations and remain available while infrastructure execution is disabled. Custom runbook authoring is intentionally not production-supported yet. The resolver boundary is independently fail-closed behind `AUTOMATION_EXECUTION_ENABLED=false`; authorization and the worker both enforce it. Execution/verification lifecycle events and decision-governance events are delivered asynchronously through the Integrations-owned Notification Channels contract. Dead-letter executions are immutable and are never replayed with consumed one-time authorization; a retry requires fresh evidence and a new candidate/decision lifecycle.

Deferred work is allowed to evolve behind those boundaries. A future feature-complete
review must add the applicable Functional, Integration, Security, Rendering, and E2E
evidence before reserved capabilities are promoted to Available or mutation execution is
enabled.


## Rule Exception / Accepted Risk governance

Rule Catalog owns time-bounded Accepted Risk governance for active recommendation findings. An exception records a canonical rule, asset scope, reason, risk/change reference, owner, expiry, and revocation evidence. It never changes the underlying recommendation truth: a non-compliant finding remains visible and searchable while AlertCase promotion is suppressed only for the active exception window.

Two scopes are supported:

- `rule_asset`: covers all current and future active findings for the same canonical rule and asset until expiry. This is the preferred scope for one shared constraint, such as many unencrypted buckets on the same Object Storage system.
- `finding_keys`: covers only explicitly selected active finding identities on one asset, allowing partial acceptance while uncovered findings remain actionable.

Overlapping active exception scopes are rejected so one finding cannot have ambiguous accepted-risk ownership. Expiry is mandatory, permanent exceptions are intentionally unsupported, and revocation releases covered findings back to normal alert eligibility on the next reconciliation cycle.

Alert Intelligence consumes this governance state; it does not redefine it. Recommendation evidence remains child-granular, while alert promotion may use the Rule Catalog grouping policy. `rule_asset` grouping creates one AlertCase per canonical rule and asset, preserves each child recommendation in `recommendation_sources`, derives severity from the highest active child, and shrinks or closes the case as individual findings clear or become covered by Accepted Risk. Existing finding-level cases are closed as `superseded` when a grouping policy change rehomes their active findings into the new grouped identity; this disposition does not claim source recovery.

## Object Storage recommendation ownership

Object Storage recommendations reuse the central Intelligence catalog and finding lifecycle; they do
not introduce a MinIO-specific Intelligence workspace. Current active MinIO-backed evaluators consume
only committed `ObjectStorageSystem` / `ObjectStorageBucket` evidence for bucket quota pressure, public
exposure review, and missing encryption configuration. The recommendation evaluator does not issue live
MinIO, Metrics Source, or Alertmanager queries. Provider identity is attached to each finding as evidence while the
canonical rule domain remains `object_storage`.

Reusable recommendation callers must scope findings with canonical `domain` + `asset_key`. Kubernetes
Dashboard explicitly requests `domain='kubernetes'`, preventing Object Storage findings from leaking
into a Kubernetes-only surface. Object Storage Analytics recommendation tabs consume the same Intelligence finding source rather than
re-implementing these rule conditions.

## Object Storage Rule Catalog coverage

Rule Catalog now records Object Storage definitions as canonical `object_storage.*` rules with explicit
provider coverage. MinIO is the currently validated provider coverage for Object Storage inventory,
forecast, and metric-signal definitions; the provider name is evidence metadata rather than a separate
rule namespace. Metric-signal catalog entries mirror the current Object Storage Analytics capacity,
request-error, waiting-request, and offline-node boundaries. The catalog schema uses a generic
`evidence_boundary` field so Metrics Source, Alertmanager, provider APIs, committed inventory, and worker
artifacts can coexist without making one backend the Intelligence schema owner.

## Alert Intelligence notification delivery

Notification Channels is an Integrations-owned provider-neutral outbound delivery layer. Telegram, SMTP email, and Microsoft Teams Workflows are the current adapters. Channel credentials are stored through `EncryptedText`; the generic persistence contract stores encrypted provider credential payload, destination, provider configuration, severity policy, and domain scope without Telegram-specific database columns.

Automatic Alert Intelligence notification polling runs on the existing maintenance worker queue. Current environment controls are:

- `KAORI_PUBLIC_BASE_URL` (canonical absolute KAORI URL used in notification links)
- `ALERT_INTELLIGENCE_NOTIFICATION_ENABLED` (default `true`)
- `ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES` (default `1`, bounded `1..60`)
- `NOTIFICATION_DELIVERY_TIMEOUT_SECONDS` (default `10`, bounded `1..60`)
- `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` (default `3`, bounded `1..10`)

An enabled channel is not eligible for automatic delivery until Test Delivery succeeds. Active-alert events are deduplicated per channel and alert episode; failed deliveries can retry up to the configured attempt ceiling. Alertmanager remains the authoritative raw routing/receiver layer. Alert Intelligence emits enriched alert events into Notification Channels; Scheduled Reports can use the same channel infrastructure for report completion events.
