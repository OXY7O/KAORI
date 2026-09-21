# KAORI Reusable Component Ownership

**Status:** Canonical ownership and extension registry for shared presentation composition.

## Purpose

KAORI reuses presentation by semantic role, not by visual similarity alone. A shared component owns the geometry, accessibility behavior, interaction contract, and reusable token bundle for one role. Domain templates supply data, copy, routes, permissions, and domain-specific evidence.

A lower file count is not a goal by itself. Components with different operator meaning remain separate even when their cards look similar.

## Ownership matrix

| Family | Canonical owner | Extension boundary |
|---|---|---|
| Hero and context | `components/page_hero.html` plus `components/HERO.md` | Domain wrappers supply evidence and actions. They do not duplicate Hero shell, context-panel, metadata, or typography geometry. |
| Readiness and operational callouts | `components/operational_callout.html`, `components/states/_blocked_state.html`, `components/states/_empty_state.html` | Use the semantic state matching the operator decision. A blocked state, empty state, and advisory callout are not interchangeable. |
| Section shells and operational metrics | `components/operational_section_card.html`, `components/operational_metric_card.html` | Domain templates provide labels and evidence; page-local copies of shared shell/metric geometry are prohibited. |
| Tables, filters, loading, empty/error, and pagination | `components/table.html`, `components/table_primitives.html`, `components/table_registry.html`, `components/pagination.html`, `components/loading_bar.html`, shared state components | Data ownership remains with the domain. Shared components own table/filter/pagination/loading geometry and interaction grammar. |
| Status labels and semantic borders | `components/table_label.html` and semantic helpers owned by the consuming shared component | Status meaning selects the tone. Domains must not create local color systems or badge geometry. |
| Forms, action bars, and destructive confirmation | `components/form_field.html`, `components/form_action_bar.html`, `components/form_with_context_rail.html`, `components/destructive_confirmation_modal.html` | Validation and persistence remain domain-owned. Field/action/confirmation composition remains shared. |
| Modal, drawer, and sheet surfaces | `components/resource_detail_modal.html`, `components/side_drawer.html`, and the shared confirmation modal | Choose by interaction semantics: focused modal, contextual drawer, or destructive confirmation. Do not merge these merely because they overlay the page. |
| Navigation and mobile action surfaces | `components/navigation/sidebar.html`, navigation partials, and shared action-button contracts | Route ownership and permissions remain with the domain; shell geometry, focus, collapse/drawer behavior, and action treatment remain shared. |
| Operational toast and notification surfaces | `components/operational_toast.html`, `components/operational_progress_toast.html`, `components/operation_feedback_oob.html` | Producers supply normalized events. Toast/progress lifecycle and OOB presentation remain shared. |
| Workspace tabs | `components/workspace_tabs.html`, `components/framed_workspace_tabs.html`, `components/segmented_tabs.html`, `components/content_tabs.html` | Select the registered semantic tab style. Domain adapters may own state/panels but never copy a registered style's geometry. |
| Context and guidance cards | `components/context_guidance_card.html`, `components/information_guide_card.html`, `components/workspace_summary_card.html`, `components/page_context_card.html` | These remain separate semantic roles. Reuse within each role; do not flatten guidance, information, summary, and page context into one generic card. |

## Framed Workspace Tabs

`components/framed_workspace_tabs.html` is the sole owner of **Tab Style 2 — Framed Workspace Tabs** geometry and ARIA tab-bar behavior.

It owns:

- the framed navigation surface;
- tablist and tab roles;
- tab button geometry;
- active/inactive visual treatment;
- badges and badge IDs;
- roving tabindex bindings;
- Left/Right/Home/End keyboard bindings;
- focus-ring treatment.

`components/integration_workspace_tabs.html` is an Integration-specific semantic adapter. It owns only:

- the fixed provider landing views `Integration Coverage` and `Connection Registry`;
- provider-specific prefix and accessible label construction;
- URL-backed selected state through the shared `integrationWorkspaceTabs(...)` controller;
- the two tab panels and their domain caller content.

The Integration adapter must call `framed_workspace_tabs.render(...)`. It must not contain its own `role="tablist"`, tab button markup, or copied framed-tab Tailwind bundle.

## Adapter rule

An adapter is allowed when a domain needs a stable semantic API around a canonical component.

An adapter may:

- translate domain data into canonical component arguments;
- provide domain-specific labels, icons, routes, counts, or panel content;
- own state that the canonical component intentionally delegates;
- add a domain marker used by tests or HTMX targeting.

An adapter must not:

- copy the canonical component's geometry or accessibility markup;
- fork keyboard/focus behavior already owned by the canonical component;
- introduce a second semantic color or spacing system;
- hide a different interaction model behind a visually similar wrapper.

If the shared component cannot represent a requirement without changing its semantics, document the exception before creating a new component.

## Composition rules

1. **Prefer an existing semantic owner.** Search the design registry and shared component directory before adding page-local markup.
2. **Extend the owner, not the consumer.** A reusable new capability belongs in the canonical component and its contract.
3. **Keep domain authority local.** Data queries, permissions, mutation rules, provider semantics, and business state remain in the domain.
4. **Do not generalize unrelated meaning.** Similar radius, border, or spacing does not make two components the same abstraction.
5. **Keep responsive and dark-mode behavior with the owner.** Consumers must not patch shared geometry independently.
6. **Use existing verification.** `verify_ui_reuse.py`, `verify_ui_style.py`, component contracts, architecture checks, and browser tests are extended instead of bypassed.

## Review checklist

Before adding or changing a UI structure:

- identify the semantic family in this registry;
- confirm which file owns geometry and interaction behavior;
- confirm whether the consumer is a direct user or a justified adapter;
- verify that no registered component geometry is copied into the consumer;
- preserve light/dark and responsive behavior through the canonical owner;
- extend the existing verifier or contract when the ownership boundary is new;
- add a new component only when the semantic role is genuinely different.
