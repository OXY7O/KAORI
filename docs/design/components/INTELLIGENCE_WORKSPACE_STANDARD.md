# Intelligence Workspace Standard

## Scope

This standard covers Intelligence Overview, Recommendations, Rule Catalog, Alert Intelligence, and Automation Control. Notification Channels is an Integrations-owned platform delivery capability consumed by Intelligence.

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

Automation Control is the governed bridge from Intelligence evidence to controlled execution. Its server-owned workspaces are **Overview**, **Runbooks**, **Decisions**, **Execution**, and **Readiness**, rendered with the shared **KAORI Content Tabs** (`components/content_tabs.html`, `render_links()` mode). The page uses a standalone **Automation Control Summary** directly below the Hero, then one **Automation Control Workspace** surface that owns tabs, active-workspace context, and the selected long-form section. Inner automation sections use divider-based hierarchy; card surfaces are reserved for comparisons, records, callouts, and forms rather than wrapping every section independently. Overview reports factual decision, execution, safety, readiness, and notification-delivery posture; it must not regress to an implementation-domain map.

Infrastructure execution is disabled by default through `AUTOMATION_EXECUTION_ENABLED=false`. Governance configuration remains available in **Governance Only** mode: operators may activate validated source-controlled System Runbooks, maintain deterministic environment bindings, review candidates, approve/reject immutable decisions, configure deployment policies and safety controls, record readiness evidence, and advance ordered rollout stages without crossing the resolver boundary. System Runbook activation validates the adapter contract shipped by the build independently from runtime `RESOLVER_ENABLED_ACTIONS`, so catalog preparation never requires enabling execution registration. Custom runbook authoring remains locked through `CUSTOM_RUNBOOK_AUTHORING_ENABLED=false` until its simulation, maturity, regression, and security contracts are production-ready. Authorization and resolver workers independently re-check the execution gate; disabled execution returns **Infrastructure Execution Disabled** feedback. `Governance Only` therefore means the control plane can be made ready while provider mutation remains fail-closed.

Decision candidates are non-executable. Promotion creates an immutable decision snapshot; approval or rejection is a distinct accountable outcome, and approval-required decisions enforce maker-checker separation. Approval and execution lifecycle notifications are queued asynchronously through matching Notification Channels; delivery failure never rewrites the recorded decision or execution outcome. Persisted decisions remain separate from execution journals. Execution Control owns resolver registry, deployment policies, safety controls, orchestration journals, post-action verification, and immutable dead letters. Production Readiness reports execution state, resolver registration, scoped deployment policy, readiness evidence, Notification Channel coverage, and ordered rollout stages independently.

The intended first controlled execution pilot remains `kubernetes.deployment.restart`. Registration alone does not make it executable: approval, namespace allowlist, registry parity, server-side dry-run, post-action rollout verification, audit, notification delivery, recovery evidence, and staged production-readiness evidence remain mandatory. Deployment restart is not transactionally reversible, so KAORI records compensating/manual recovery evidence rather than claiming an automatic rollback.


## Intelligence Overview

`Intelligence Overview` is the landing workspace for the Intelligence category. It summarizes committed recommendation posture, registered asset coverage for Alert Intelligence, canonical Rule Catalog coverage, and governed Automation Control posture without issuing live infrastructure-provider queries.

The Overview must preserve capability ownership:

- **Recommendations** owns catalog-backed findings from committed KAORI evidence.
- **Alert Intelligence** resolves provider alert state on demand and keeps Alertmanager/Metrics Source lifecycle ownership explicit.
- **Rule Catalog** owns canonical detection, evidence-boundary, provider-coverage, severity, and operator-response definitions.
- **Automation Control** owns runbooks, decisions, approvals, readiness, controlled execution, verification, and recovery.

The Overview may surface top recommendation priorities and lightweight control posture, but it must not duplicate alert retrieval, execute automation, or become another analytics provider client.


### Intelligence Overview committed-evidence posture and alert semantics (#1490–#1492)

- **Active AlertCase** is the source-qualified recommendation-origin condition `workflow_state != closed` **and** `source_state in (firing, unknown)`; resolved-source cases remain available in Alert Intelligence history, not Active. Critical and warning counts require **firing** evidence. Source-unknown remains an attention state and must not become false critical or green.
- Pending Automation candidates and pending approval decisions are actionable only while `expires_at > now`. Post-action verification failures are counted in operational control attention even if resolver execution returned `succeeded`. The shared SQL-grouped verification projection is used by Intelligence Overview and Automation Control.
- **Evidence Freshness** is a conservative **24-hour committed Inventory baseline** for managed Kubernetes, Object Storage, and enabled/active Registry instances; it is *not* a guarantee of scan/security/metrics/rule evaluator coverage. The Overview must not say `Operationally Clear` merely because no findings exist. Incomplete recent Inventory produces `Evidence Review Required`; complete inventory with no findings is `No Active Findings`, not a provider-health claim.
- Alert notification delivery rows stay auditable. Only failed alert-operation deliveries updated during the past 24 hours affect the current Overview control-attention summary; a successful retry transitions its row to `sent`. Historic failures remain in Notification Channels.
- The Overview remains a SQL/committed-evidence projection; there is no provider request, automatic corrective action, or parallel Intelligence rule engine on page load. Live UAT must also validate collection lag, record expiry, failed verification and source-unknown transitions before acceptance.

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
- Active Object Storage recommendation evaluators consume committed evidence only. Intelligence must not issue live MinIO, Metrics Source, or Alertmanager queries to construct recommendation findings.
- A finding with no active match is not equivalent to runtime health. Recommendation posture uses `No Active Findings` rather than claiming infrastructure health.

## Rule Catalog provider-coverage contract

- Rule keys remain canonical to the asset domain. Object Storage definitions use the `object_storage.*` namespace; current MinIO support must not create a parallel `minio.*` rule namespace unless a rule is genuinely exclusive to MinIO semantics.
- Provider coverage is implementation evidence. It identifies which provider adapters/evidence paths currently satisfy a rule definition and must not change the canonical rule namespace.
- The catalog may filter by provider coverage, but a provider filter does not imply that the rule condition itself is provider-specific.
- Rule definitions use a generic `evidence_boundary` contract. Metrics Source, Alertmanager, provider APIs, committed inventory, and worker-materialized artifacts are evidence sources; no single backend owns the catalog schema.
- Object Storage metric-signal definitions must stay aligned with the thresholds used by Object Storage Analytics. Threshold changes require coordinated updates to analysis behavior, catalog definition, recommendation semantics where applicable, and contract tests.

### Alert Intelligence source-aware read model and posture (#1513)

Active and resolved queues are paginated by the shared SQL pagination utility **before** case serialization (default 5, options 5/10/25/50). Owner relationships and active-silence evidence are fetched in bounded page batches; aggregate counts are source-state scoped SQL projections. Read-only detail access is constrained to the selected domain and asset, not a fleet scan. Silence registries must include only recommendation-origin AlertCases.

Source State is an **independent** filter from Severity. The Source Unknown shortcut, form, URL and HTMX pagination must all carry `source_state=unknown`, never `severity=unknown`. Modal mutation forms must also preserve `source_state` when refreshing the queue after an operator action. Resolved Today means **source recovery recorded**, not necessarily verified case closure. Alert Intelligence delivery failures and Intelligence Overview attention use the same current 24-hour failed-delivery window, retaining older failures in the immutable journal.

The overview must never state Operationally Clear solely because active cases are zero. A conservative 24-hour committed-inventory readiness label is not proof that all recommendation, scan or alert workers completed successfully. Missing/partial source evidence warrants Evidence Review Required; complete inventory with zero cases is merely No Open Cases Observed. Continue to use the shared Violet Hero, Resource Detail Modal, access gates, contextual HTMX and accessible feedback components.

## Alert Intelligence and outbound notification ownership

Alert Intelligence is a read-oriented, asset-scoped interpretation workspace. Kubernetes and Object Storage consume their existing alert-source contracts: Automatic mode prefers Alertmanager and may fall back to Metrics Source alert evidence. Provider alert lifecycle, KAORI recommendations, and catalog rules must remain distinguishable; contextual correlation must never be presented as causal attribution without evidence.

The Alert Intelligence page keeps the **Alert Intelligence Summary** visible as global posture, then uses one **Alert Intelligence Workspace** surface. Inside that workspace, the shared **KAORI Content Tabs** (`components/content_tabs.html`, server-owned `render_links()` mode) appear immediately below the workspace header for **Alert Records**, **Correlation & Guidance**, **Notification Delivery**, and **Evidence & Ownership**. A compact **Operational Context** row follows the tabs and owns domain, asset, and source policy for every section. This ordering is canonical: section navigation answers *where the operator is*, Operational Context answers *which asset/source the section describes*, and the active section answers *what evidence is available*. Alert Intelligence must not maintain a page-local tab style or adopt the Analytics client controller; URL/HTMX state remains server-owned while the shared component owns visual geometry. Active tab content must remain inside the same outer workspace surface rather than creating a second standalone section card below it. Search, severity, and lifecycle-state controls are record filters and belong only inside **Alert Records**; they refresh automatically through HTMX, there is no Apply/Filter submit action, and a compact **Reset Filters** action remains available while preserving domain, asset, and source. Each tab must carry its own informative context rather than acting as a label-only container: Alert Records exposes resolved source/runtime/lifecycle authority, Correlation exposes recommendation/rule counts plus the non-causal boundary, Notification Delivery exposes channel/delivery posture, and Evidence & Ownership exposes detection/lifecycle/interpretation/execution authority. Record pagination remains local to the Alert Records table.

Notification Channels is owned by **Integrations** at `/integrations/notification-channels`. Alert Intelligence emits governed `alert_intelligence.active_alert` events into that shared delivery layer; it does not own provider credentials, transport adapters, or channel lifecycle. Alertmanager remains responsible for raw alert grouping, inhibition, silences, routing, and receiver delivery. Recent Alert Intelligence delivery evidence shown for a selected asset must be filtered by the current domain + asset identity rather than mixing unrelated asset deliveries into the workspace.

The provider contract must remain extensible so future Slack, generic webhook, or additional enterprise messaging adapters can be added without changing Alert Intelligence semantics. Microsoft Teams delivery uses the Teams Workflows / Power Automate webhook contract rather than legacy Office 365 connector URLs. SMTP email supports STARTTLS, TLS/SMTPS, and trusted-relay operation. The dispatcher sends first-seen active alert episodes that match channel policy and deduplicates them per channel/event identity. Resolved-event delivery is not part of the current outbound contract and must not be implied by UI status or delivery history.

### Rule Catalog filtered posture and HTMX coherence (#1524)

Rule Catalog summary, Hero counts, and posture describe **matching canonical definitions after all filters**, not global engine readiness or connected provider health. `Available` means a definition has an implemented KAORI evaluator/evidence boundary, not that a current provider observation succeeded. A reserved-only selection reports Reserved Plan, imported-only reports Imported Signal, and zero matches report No Matching Rules; mixed nonavailable definitions report Catalog Only. Scope labels identify filtered views. The server-owned Hero and Summary use out-of-band HTMX refresh alongside the results; standard full-page rendering remains authoritative on reload and history restoration. Do not introduce provider-live readiness checks or a second rule catalog.

### Rule Catalog page-size and escalation controls (#1525)

The shared Intelligence result pagination can replace only the results region. On Rows changes, the response must also update the corresponding hidden per_page input in the separate filter form through a scoped HTMX out-of-band element; Recommendations and Rule Catalog retain the same default of 5 and supported 5/10/25/50 values. URL navigation, filter changes, and reset retain the selected page size. Reserved Plan and Imported Signal definitions are read-only and never display an editable escalation form, even to authorized decision users; the Available-only server-side mutation guard remains authoritative.
