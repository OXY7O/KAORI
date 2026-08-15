# Automation Control Final Recheck — 2026-08-15

## Scope

Automation Control was redesigned as one governed workspace rather than a stack of independent dashboard cards. The redesign is presentation-only and preserves the existing execution, approval, readiness, recovery, and notification boundaries.

## Final information architecture

1. Hero — stable Automation Control identity and current control posture.
2. Automation Control Summary — governance queue, active execution, and failure posture.
3. Automation Control Workspace — shared KAORI Content Tabs plus one selected long-form workspace.
4. Active workspace content — divider-owned sections; cards are reserved for records, comparisons, forms, and callouts.

Server-owned Content Tabs: Overview, Runbooks, Decisions, Execution, Readiness.

## Preserved control boundaries

- `AUTOMATION_EXECUTION_ENABLED` remains default-deny.
- Governance configuration remains available while infrastructure execution is disabled.
- System Runbooks remain source-controlled and validated; custom authoring remains locked.
- Decision candidates remain non-executable; promotion creates immutable decision evidence.
- Approval-required decisions retain maker-checker separation.
- Execution authorization remains one-time and is revalidated by worker-side policy/readiness/safety gates.
- Verification is independent from API execution success.
- Recovery remains compensating/manual where transactional rollback is not truthful.
- Notification delivery remains asynchronous and provider-neutral.

## UI outcome

The previous metric strip was replaced by a standalone summary box. The old page-local underline tabs were replaced by `components/content_tabs.html` in server-owned `render_links()` mode. Overview terminology was simplified to Control Path, Safety & Readiness, and Current Activity. Long-form tabs now share one workspace surface to reduce card nesting and improve reading hierarchy.
