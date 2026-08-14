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
under `app/automation_control/`, not by this domain. It coordinates read models
and governed commands across Knowledge, Intelligence, Resolver, and Production
Readiness without making those domains import one another. The application layer
may call Intelligence public use cases; Intelligence must not import the
Automation Control package.

Route: `/intelligence/automation-control`

See `docs/architecture/domain-20-automation-control-center-ui.md`.

## KAORI Violet presentation standard

All Intelligence workspaces use the KAORI Violet Infrastructure design system.
Recommendations, Catalog, Alert Intelligence, and the cross-domain Automation
Control Center share a solid violet hero, a right-side posture card, tokenized
surfaces and borders, `rounded-xl` sections, `rounded-lg` internal object blocks,
violet focus states, and compact rectangular status/metadata labels. Semantic
green, amber, red, cyan, and slate remain reserved for operational state,
priority, or risk; decorative blue gradients and literal slate surfaces must not
be reintroduced.

## Intelligence Workspace Presentation

Recommendations, Rule Catalog, Alert Intelligence, and Automation Control use the canonical Intelligence workspace contract documented in `docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md`.

Automation Control is the governed bridge from Intelligence evidence to controlled execution. Its current UI exposes factual **Governance Only** state across Overview, Runbooks & Bindings, Decision Review, Execution Control, and Production Readiness. Decision governance is active: candidates may be promoted or dismissed, accountable approvals/rejections are persisted, and approval lifecycle notifications are emitted through Notification Channels. Resolver execution and execution-control mutations remain disabled by default behind `AUTOMATION_CONTROL_MUTATIONS_ENABLED`; the guard is intentionally not exposed as an environment-configured release toggle in this baseline. Enabling infrastructure mutation requires a later feature-complete review with allowlist, dry-run, rollback, verification, notification, audit, and E2E evidence.

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
- **Alert Intelligence** is active for Kubernetes and Object Storage. Automatic alert-source selection prefers Alertmanager and falls back to Prometheus `ALERTS`; committed Recommendations and Rule Catalog definitions provide contextual enrichment without asserting causal correlation. Server and HCI enrichment remain **Reserved Plan**.
- **Notification Channels** is owned by Integrations, not Intelligence. Alert Intelligence consumes the platform delivery contract while Alertmanager remains the raw alert routing/receiver authority.
- **Automation Control** is an application-layer orchestration surface. Candidate promotion/dismissal and decision approval/rejection are active governance operations and are not controlled by the infrastructure mutation gate. Resolver execution, execution-control policy changes, runbook authoring changes, dead-letter requeue, and rollout/readiness mutations remain fail-closed behind `AUTOMATION_CONTROL_MUTATIONS_ENABLED`, which must remain unset/default-false in this baseline. The approved current posture is **Governance Only / Infrastructure Mutation Disabled**. Approval-required, decision-approved, and decision-rejected events are delivered asynchronously through the Integrations-owned Notification Channels contract.

Deferred work is allowed to evolve behind those boundaries. A future feature-complete
review must add the applicable Functional, Integration, Security, Rendering, and E2E
evidence before reserved capabilities are promoted to Available or mutation execution is
enabled.


## Object Storage recommendation ownership

Object Storage recommendations reuse the central Intelligence catalog and finding lifecycle; they do
not introduce a MinIO-specific Intelligence workspace. Current active MinIO-backed evaluators consume
only committed `ObjectStorageSystem` / `ObjectStorageBucket` evidence for bucket quota pressure, public
exposure review, and missing encryption configuration. The recommendation evaluator does not issue live
MinIO, Prometheus, or Alertmanager queries. Provider identity is attached to each finding as evidence while the
canonical rule domain remains `object_storage`.

Reusable recommendation callers must scope findings with canonical `domain` + `asset_key`. Kubernetes
Dashboard explicitly requests `domain='kubernetes'`, preventing Object Storage findings from leaking
into a Kubernetes-only surface. Future Object Storage Analytics recommendation tabs must consume the
same Intelligence finding source rather than re-implementing these rule conditions.

## Object Storage Rule Catalog coverage

Rule Catalog now records Object Storage definitions as canonical `object_storage.*` rules with explicit
provider coverage. MinIO is the currently validated provider coverage for Object Storage inventory,
forecast, and metric-signal definitions; the provider name is evidence metadata rather than a separate
rule namespace. Metric-signal catalog entries mirror the current Object Storage Analytics capacity,
request-error, waiting-request, and offline-node boundaries. The catalog schema uses a generic
`evidence_boundary` field so Prometheus, Alertmanager, provider APIs, committed inventory, and worker
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
