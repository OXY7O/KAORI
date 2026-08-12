# KAORI Design System v1.0

This document is the entry point for KAORI's interface contract. New modules must reuse these rules before introducing local variants.

## Foundations

- `components/TYPOGRAPHY.md` — type scale, casing, weight, technical text.
- `components/COLOR_AND_SEMANTIC.md` — brand and semantic colors.
- `components/DARK_MODE.md` — locked neutral-first dark surface and Violet-emphasis contract.
- `components/SPACING.md` — layout rhythm and density.
- `components/ICONS.md` — icon hierarchy and contextual use.
- `components/ACCESSIBILITY.md` — focus, labels, states, keyboard behavior.
- `components/RESPONSIVE_AND_HTMX.md` — responsive and partial-update behavior.

## Components

- `components/HERO.md`
- `components/ANALYTICS_HERO.md` — domain extension for Kubernetes Analytics hero content.
- `components/CARD.md`
- `components/TABLE_AND_LABEL.md`
- `components/FORM.md`
- `components/FORM_ACTION_BAR.md`
- `components/CONTEXT_GUIDANCE_CARD.md`
- `components/INFORMATION_GUIDE_CARD.md`
- `components/WORKSPACE_SUMMARY_CARD.md`
- `components/HEALTH_INTERPRETATION.md`
- `components/BUTTON.md`
- `components/PAGINATION.md`
- `components/EMPTY_ERROR_STATE.md`
- `components/LOADING.md`
- `components/MODAL_DRAWER.md`
- `components/EXPANDABLE.md`
- `components/INFO_FLOW.md`
- `components/RELATED_PAGE_CARD.md`
- `components/CONNECTION_VALIDATION_HEADER.md`
- `components/OPERATIONAL_TOGGLE.md`
- `components/OPERATIONAL_ACTION_FEEDBACK.md`
- `components/SIDEBAR_NAVIGATION.md` — locked v1.3 sidebar hierarchy, geometry, and information architecture.

## Global guardrail

A local component variant is allowed only when the existing semantic role cannot represent the requirement. The reason and exception must be documented before implementation.

### Integration Manage Workspace

Provider instance management uses the shared four-tab contract documented in `components/INTEGRATION_MANAGE_WORKSPACE.md`. Configuration is inline; Validation exposes technical evidence; Runtime uses shared health/history; Scope exposes governed bindings and resolution.

### Operational action feedback

Persisted provider actions use the shared HTMX, toast, and Activity Audit contract documented in `components/OPERATIONAL_ACTION_FEEDBACK.md`. Same-page mutations update their workspace partial; registration and successful deletion may use `HX-Redirect`.
