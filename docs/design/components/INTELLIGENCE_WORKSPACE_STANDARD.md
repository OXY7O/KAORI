# Intelligence Workspace Standard

## Scope

This standard covers Recommendations, Rule Catalog, Alert Intelligence, and Automation Control.

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
