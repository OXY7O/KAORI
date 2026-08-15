# Intelligence Workspace Standard

## Scope

This standard covers Recommendations, Rule Catalog, Alert Intelligence, and Automation Control. Notification Channels is an Integrations-owned platform delivery capability consumed by Intelligence.

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

Automation Control is the governed bridge from Intelligence evidence to a future controlled execution path. Its workspaces are **Overview**, **Runbooks & Bindings**, **Decision Review**, **Execution Control**, and **Production Readiness**. Overview reports factual decision, execution, safety, readiness, and notification-delivery posture; it must not regress to an implementation-domain map.

Infrastructure execution is disabled by default through `AUTOMATION_EXECUTION_ENABLED=false`. Governance configuration remains available in **Governance Only** mode: operators may activate validated source-controlled System Runbooks, maintain deterministic environment bindings, review candidates, approve/reject immutable decisions, configure deployment policies and safety controls, record readiness evidence, and advance ordered rollout stages without crossing the resolver boundary. System Runbook activation validates the adapter contract shipped by the build independently from runtime `RESOLVER_ENABLED_ACTIONS`, so catalog preparation never requires enabling execution registration. Custom runbook authoring remains locked through `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false` until its simulation, maturity, regression, and security contracts are production-ready. Authorization and resolver workers independently re-check the execution gate; disabled execution returns **Infrastructure Execution Disabled** feedback. `Governance Only` therefore means the control plane can be made ready while provider mutation remains fail-closed.

Decision candidates are non-executable. Promotion creates an immutable decision snapshot; approval or rejection is a distinct accountable outcome, and approval-required decisions enforce maker-checker separation. Approval and execution lifecycle notifications are queued asynchronously through matching Notification Channels; delivery failure never rewrites the recorded decision or execution outcome. Persisted decisions remain separate from execution journals. Execution Control owns resolver registry, deployment policies, safety controls, orchestration journals, post-action verification, and immutable dead letters. Production Readiness reports execution state, resolver registration, scoped deployment policy, readiness evidence, Notification Channel coverage, and ordered rollout stages independently.

The intended first controlled execution pilot remains `kubernetes.deployment.restart`. Registration alone does not make it executable: approval, namespace allowlist, registry parity, server-side dry-run, post-action rollout verification, audit, notification delivery, recovery evidence, and staged production-readiness evidence remain mandatory. Deployment restart is not transactionally reversible, so KAORI records compensating/manual recovery evidence rather than claiming an automatic rollback.

## Baseline lock semantics

The Intelligence surface may be baseline-locked while feature delivery is still in
progress. Baseline lock means the currently implemented read/evidence contracts, security
boundaries, shared UI ownership, and explicit Reserved Plan states are stable. It does
**not** mean every planned evaluator, provider integration, or automation mutation is
feature-complete.

A capability must remain `Reserved Plan` until its provider, validation, behavioral, and
release-test contracts are complete. Automation Control keeps infrastructure execution
fail-closed by default through an explicit environment-controlled execution switch, while
governance preparation stays operational. Enabling that switch does not bypass deployment
policy, readiness, safety, authorization, dry-run, worker revalidation, or verification gates,
and route/model scaffolding alone must never be interpreted as execution readiness.
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
- Rule Catalog Hero remains provider-neutral. Provider-specific coverage such as MinIO belongs in filters, row metadata, and rule detail evidence—not in the page identity or Hero posture metrics.
- Rule definitions use a generic `evidence_boundary` contract. Prometheus, Alertmanager, provider APIs, committed inventory, and worker-materialized artifacts are evidence sources; no single backend owns the catalog schema.
- Object Storage metric-signal definitions must stay aligned with the thresholds used by Object Storage Analytics. Threshold changes require coordinated updates to analysis behavior, catalog definition, recommendation semantics where applicable, and contract tests.

## Alert Intelligence and outbound notification ownership

Alert Intelligence is a read-oriented, asset-scoped interpretation workspace. Kubernetes and Object Storage consume their existing alert-source contracts: Automatic mode prefers Alertmanager and may fall back to Prometheus `ALERTS`. Provider alert lifecycle, KAORI recommendations, and catalog rules must remain distinguishable; contextual correlation must never be presented as causal attribution without evidence.

Notification Channels is owned by **Integrations** at `/integrations/notification-channels`. Alert Intelligence emits governed `alert_intelligence.active_alert` events into that shared delivery layer; it does not own provider credentials, transport adapters, or channel lifecycle. Alertmanager remains responsible for raw alert grouping, inhibition, silences, routing, and receiver delivery.

The provider contract must remain extensible so future Slack, generic webhook, or additional enterprise messaging adapters can be added without changing Alert Intelligence semantics. Microsoft Teams delivery uses the Teams Workflows / Power Automate webhook contract rather than legacy Office 365 connector URLs. SMTP email supports STARTTLS, TLS/SMTPS, and trusted-relay operation. The dispatcher sends first-seen active alert episodes that match channel policy and deduplicates them per channel/event identity. Resolved-event delivery is not part of the current outbound contract and must not be implied by UI status or delivery history.
