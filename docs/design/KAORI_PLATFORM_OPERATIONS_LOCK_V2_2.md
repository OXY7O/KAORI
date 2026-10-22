# KAORI Platform Operations Final Lock v2.2

v2.2 supersedes v2.1 for two reviewed refinements:

1. Data Lifecycle v1.3 admits the approved `analytics_snapshot` archive adapter with stale-serve protection.
2. Platform Overview v1.1 adopts the redesigned KAORI workspace-posture presentation and the explicit **Kubernetes Administration** navigation label.

Jobs & Executions, Archive Storage, Runtime Observation lifecycle coverage, Activity Audit lifecycle coverage, and Secret Reveal authorization/security contracts remain unchanged.

## Kubernetes Administration tab-family refinement — 2026-10-22 REVIEW/UAT candidate

The earlier Platform Operations Lock v1 defined `Framed Workspace Tabs` for Kubernetes Administration. Operator Visual QA under [#2605](https://github.com/OXY7O/KAORI/issues/2605) rejected the enclosing parent card around the peer `Overview` / `Secret Reveal` views. The current KAORI Page Archetype and Tab Style registry already owns the appropriate alternative: **Tab Style 1 — Integrated Workspace Tabs** (`components/workspace_tabs.html`) for peer sections of the same operational capability. This is a narrow **variant selection**, not a new tab style or exception to accessibility, Violet, or source governance.

For Kubernetes Administration only, use the existing Integrated tab bar with a single divider and **no framed parent workspace surface**. Overview readiness cards and Secret Reveal controls own their independent canonical operational card shells. The existing `activeTab/setTab/moveTab`, URL-backed `tab` state, `kubernetes:load-secret-reveal` lazy HTMX event, panel `aria-labelledby`/tab `aria-controls`, Arrow/Home/End keyboard behavior, all nine posture OOB IDs, and RBAC/CSRF/namespace policy constraints are preserved. Jobs & Executions, Data Lifecycle and Integration workspaces retain their separately approved Framed Workspace Tabs.

The matching scoped verifier/contract change is part of the same #2605 review candidate, and does not relax the Platform Operations security, authorization, and pagination gates. It requires actual DevContainer screenshot/keyboard/HTMX UAT and Human Acceptance before official staging admission; normal `kaori/staging`/main lock authority remains untouched until a subsequent gated promotion.
