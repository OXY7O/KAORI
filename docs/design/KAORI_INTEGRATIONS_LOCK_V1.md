# KAORI Integrations Lock v1

Status: Locked baseline
Date: 2026-08-08

## Locked Scope

This lock applies to the Integration workspaces that have completed final visual and interaction refinement:

- Integrations Overview and Runtime Overview;
- Kubernetes Integration registry and detail workspaces;
- Metrics Source registry, configuration, validation/capability, runtime, bindings/consumers, and lifecycle surfaces;
- Alertmanager registry, configuration, validation/capability, runtime, bindings/consumers, and lifecycle surfaces;
- shared provider capability/readiness components;
- shared Recent Runtime Observations table and detail modal;
- shared Integration `View More`, loading, pagination, provider-tab, configuration-decision, and runtime-detail interaction contracts;
- Kubernetes minimum-validation RBAC example and optional governed Secret-reader boundary.

This lock freezes presentation and interaction architecture. Provider-specific factual evidence, compatibility profiles, capability definitions, runtime values, and operational status may continue to evolve without reopening the design contract.

## Frozen Workspace Architecture

### Capability and Validation

Kubernetes, Metrics Source, and Alertmanager use the same shared capability-readiness presentation contract:

```text
Capability Readiness
  -> coverage / provider facts
  -> Operational Gate
  -> Evidence Boundary
  -> Next Operational Action

Capability Registry
  -> Search / Requirement / Validation Status
  -> canonical KAORI table
  -> canonical pagination
  -> shared View More modal
```

Rules:

- `app/templates/integrations/components/_capability_readiness.html` owns capability-readiness geometry and color treatment.
- Provider registries use one real HTMX request path for search, filters, rows, and pagination.
- Each registry owns exactly one shared KAORI loading bar. Synthetic Alpine timers or page-local fake loading states are prohibited.
- Default rows remain 5 with `5 / 10 / 25 / 50` choices.
- `View More` uses the shared Integration record action and shared record-detail modal shell.
- Provider technical queries/requests appear only in the Technical Verification boundary; they are not duplicated across modal cards.

### Runtime Health and Diagnostics

Runtime design follows the same mental model across providers:

```text
Runtime Decision
  -> Runtime Posture
  -> Current Runtime Gate
  -> Validation Readiness
  -> Observation Context
  -> Primary Finding
  -> Next Operational Action
  -> Evidence Handoff

Runtime Evidence
  -> lifecycle/provider context
  -> concise diagnostics

Recent Runtime Observations -> View More
  -> full immutable technical evidence and remediation
```

Rules:

- Current workspace error text is concise; full diagnostic detail belongs in the runtime-observation modal.
- Runtime Health, Connection State, Validation Readiness, and Binding Resolution remain separate evidence dimensions.
- Runtime Observation detail uses `integrations/components/_record_detail_modal.html` with standard sizing. A second standalone dialog shell is prohibited.
- Failed/blocked Diagnostic Review presents technical evidence once and one shared `Recommended Action` guidance surface.

### Configuration

Configuration is the deliberate exception to the full-width decision pattern:

```text
Connection Configuration | Configuration Decision
```

The main form remains the working surface while the shared side decision panel provides compact contract facts, change impact, controlled flow, and consumer boundary.

Rules:

- Metrics Source and Alertmanager use `integrations/components/_configuration_decision.html`.
- The canonical desktop rail is 25rem and 27rem at 2xl.
- Left and right surfaces stretch to the same visual height.
- Save actions use the embedded form-action footer; a floating nested action card is prohibited.

### Bindings and Consumers

- Registered binding count is independent of source runtime health. Provider badges count registered `binding_rows`; a disconnected or failed source can still have registered bindings.
- Source Readiness, Binding Validation, and Effective Resolution remain separate.
- Metrics Source and Alertmanager Binding Decision is horizontal and full width.
- Effective Consumer Resolution is full width; only genuinely deeper candidate evidence may use local disclosure.
- Destructive lifecycle actions remain secondary to guardrail explanation and must honor disabled state when removal is blocked.

### Tables, Loading, and Pagination

- Canonical tables use shared KAORI table primitives.
- Registries avoid forced desktop horizontal scrolling when proportional columns can preserve evidence.
- Technical code/query evidence may scroll inside its own bounded evidence surface.
- Loading bar position is `header -> loading -> filters -> table -> pagination`.
- Pagination uses resource-aware `Showing a–b of n`, default 5 rows, and 5/10/25/50 choices.

### Shared Detail Actions

`app/templates/integrations/components/_record_actions.html` owns Integration record-detail actions:

- shared `table_ui.action_classes()`;
- compact rectangular geometry;
- trailing `chevron-right`;
- optional `role` keyword retained for semantic data markers;
- provider-local oversized `View More` styling is prohibited.

### Kubernetes RBAC Boundary

Minimum Full Validation reader explicitly excludes cluster-wide Secret reads.

Optional Secret access is a separate namespace-scoped `Role + RoleBinding`, visible in its own modal tab and intended only for approved governance workflows. It must never be merged into the baseline validation `ClusterRole`.

## Frozen Visual Contract

- KAORI Violet owns brand identity and interaction emphasis; semantic colors represent operational state only.
- Dark mode uses the global token contract. Provider pages do not define private dark palettes.
- Contextual related-workspace surfaces may remain deep Violet in dark mode through shared KAORI contextual-brand ownership.
- Visible headings, table headers, form labels, modal titles, tabs, and buttons use Title Case.
- Raw Tailwind palette utilities, raw hex colors, inline `style=`, and inline DOM handlers are prohibited in locked Integration templates.
- Shared components own geometry whenever the same concept appears across Kubernetes, Metrics Source, and Alertmanager.

## Dead / Legacy Paths Removed

The final lock removes obsolete presentation paths that were no longer referenced after modal/runtime/capability consolidation:

- `app/templates/integrations/partials/_runtime_detail_content.html`
- `app/templates/metrics/partials/_analytics_readiness.html`

Previously retired Integration compatibility paths remain registered in `scripts/cleanup_obsolete_files.sh` and are protected by the final verifier.

## Change Policy

After this lock, structural redesign is not a normal maintenance change. A future design-contract change requires, in the same commit:

1. design-system documentation update;
2. explicit rationale in a lock/audit document;
3. verifier and contract-test update;
4. regression coverage for the changed behavior;
5. no silent style-debt baseline increase.

Normal post-lock work should prefer defect fixes, content corrections, provider capability additions, backend/data improvements, and security fixes without changing the frozen workspace architecture.

## Enforcement

Run:

```bash
python scripts/verify_integrations_final_lock.py
pytest -q tests/contracts/integrations
python scripts/verify_dark_mode_standard.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_core_workspace_legacy_cleanup.py
python scripts/verify_python_syntax.py
python scripts/verify_ui_style.py
```

Repository-wide `verify_ui_style.py` may still report explicitly tracked debt in unrelated domains such as Notifications or Reports. The Integration lock does not permit new Integration debt.
