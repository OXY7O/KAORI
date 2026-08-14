# Intelligence Workspace Standard

## Scope

This standard covers Recommendations, Rule Catalog, Alert Intelligence, Notification Channels, and Automation Control.

## Hero

- Inventory-aligned composition.
- Maximum three metadata labels.
- Maximum two posture metrics.
- Stable posture title with one semantic badge.

## Records

- Responsive evidence records are the default.
- Native details are used for evidence expansion; no page-local JavaScript toggle implementation.
- Pagination uses `Showing a–b of n`, `Rows`, numeric pages, Previous, and Next.

## Capability states

- `Available`: implemented evidence or evaluator path.
- `Imported Signal`: evidence originates from an authoritative external source.
- `Reserved Plan`: disabled until provider, validation, and behavior contracts are complete.

MVP, placeholder, preview-only, and coming-soon labels are prohibited.

## Automation Control

Automation Control is presentation-complete but mutation-disabled by default. The runtime guard key is `AUTOMATION_CONTROL_MUTATIONS_ENABLED`; missing configuration resolves to false. Environment-level enablement is intentionally outside the current baseline lock. Direct POST requests are rejected with a Reserved Plan notification while disabled.

## Baseline lock semantics

The Intelligence surface may be baseline-locked while feature delivery is still in
progress. Baseline lock means the currently implemented read/evidence contracts, security
boundaries, shared UI ownership, and explicit Reserved Plan states are stable. It does
**not** mean every planned evaluator, provider integration, or automation mutation is
feature-complete.

A capability must remain `Reserved Plan` until its provider, validation, behavioral, and
release-test contracts are complete. In particular, Automation Control must remain
fail-closed by default, must not gain an environment-configured enablement switch during
this baseline lock, and must not be re-labelled as Available solely because route or model
scaffolding exists.
## Multi-domain recommendation contract

- Recommendations are owned by the central Intelligence evaluator and may contain findings from multiple asset domains.
- Domain-specific consumers must request findings using canonical `domain` + `asset_key` scope; a Kubernetes-only surface must not consume unscoped Object Storage findings.
- Object Storage rules remain canonical `object_storage` rules. Provider identity such as MinIO is finding evidence, not a separate Intelligence workspace or rule namespace unless the rule is genuinely provider-exclusive.
- Active Object Storage recommendation evaluators consume committed evidence only. Intelligence must not issue live MinIO, Prometheus, or Alertmanager queries to construct recommendation findings.
- A finding with no active match is not equivalent to runtime health. Recommendation posture uses `No Active Findings` rather than claiming infrastructure health.

## Rule Catalog provider-coverage contract

- Rule keys remain canonical to the asset domain. Object Storage definitions use the `object_storage.*` namespace; current MinIO support must not create a parallel `minio.*` rule namespace unless a rule is genuinely exclusive to MinIO semantics.
- Provider coverage is implementation evidence. It identifies which provider adapters/evidence paths currently satisfy a rule definition and must not change the canonical rule namespace.
- The catalog may filter by provider coverage, but a provider filter does not imply that the rule condition itself is provider-specific.
- Rule definitions use a generic `evidence_boundary` contract. Prometheus, Alertmanager, provider APIs, committed inventory, and worker-materialized artifacts are evidence sources; no single backend owns the catalog schema.
- Object Storage metric-signal definitions must stay aligned with the thresholds used by Object Storage Analytics. Threshold changes require coordinated updates to analysis behavior, catalog definition, recommendation semantics where applicable, and contract tests.

## Alert Intelligence and outbound notification ownership

Alert Intelligence is a read-oriented, asset-scoped interpretation workspace. Kubernetes and Object Storage consume their existing alert-source contracts: Automatic mode prefers Alertmanager and may fall back to Prometheus `ALERTS`. Provider alert lifecycle, KAORI recommendations, and catalog rules must remain distinguishable; contextual correlation must never be presented as causal attribution without evidence.

Notification Channels is a separate governed mutation boundary under `/intelligence/notification-channels`. Channel configuration requires integration-management permission because it stores external delivery credentials. Telegram is the first provider adapter. Bot credentials must use KAORI encrypted credential storage, must never be rendered back into HTML or logs, and a successful test delivery is required before an enabled channel is eligible for automatic Alert Intelligence delivery. Alertmanager remains responsible for raw alert grouping, inhibition, silences, routing, and receiver delivery; KAORI channels deliver enriched Intelligence context and do not replace Alertmanager receiver configuration.

The provider contract must remain extensible so future Slack, Teams, email, or webhook adapters can be added without changing Alert Intelligence semantics. The initial dispatcher sends first-seen active alert episodes that match channel policy and deduplicates them per channel/event identity. Resolved-event delivery is not part of the initial Telegram contract and must not be implied by UI status or delivery history.
