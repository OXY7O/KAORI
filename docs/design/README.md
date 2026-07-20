# KAORI UI Documentation

## Global source of truth

- `KAORI_DESIGN_SYSTEM.md` — universal visual and interaction rules.

## Component contracts

- `components/HERO.md`
- `components/BUTTON.md`
- `components/TABLE_AND_LABEL.md`
- `components/SIDEBAR_NAVIGATION.md`
- `components/INFO_FLOW.md`
- `components/RELATED_PAGE_CARD.md`
- `components/CONNECTION_VALIDATION_HEADER.md`
- `components/OPERATIONAL_TOGGLE.md`
- `components/FORM_ACTION_BAR.md`
- `components/CONTEXT_GUIDANCE_CARD.md`
- `components/INFORMATION_GUIDE_CARD.md`
- `components/WORKSPACE_SUMMARY_CARD.md`
- `components/HEALTH_INTERPRETATION.md`

## Reusable page patterns

- `patterns/INVENTORY_AND_OPERATIONAL_PAGES.md`

## Domain specifications

Domain-specific UI rules live under `docs/modules/` or the owning module README. They may define page content, columns, metrics, actions, and provider workflows, but they may not override global tokens or shared component geometry.

## Placement rule

Use this test before adding documentation:

- Applies everywhere → global Design System.
- Applies to one reusable component → component standard.
- Applies to several modules with the same structure → page pattern.
- Mentions a provider, object type, route, column, metric, or domain action → module specification.

- [`components/PAGINATION.md`](components/PAGINATION.md)

## Current audits

- `audits/PROMETHEUS_STYLE_AND_LIFECYCLE_AUDIT_2026_07.md`
