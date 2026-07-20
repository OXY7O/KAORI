# KAORI Design System v1.0

This document is the entry point for KAORI's interface contract. New modules must reuse these rules before introducing local variants.

## Foundations

- `components/TYPOGRAPHY.md` — type scale, casing, weight, technical text.
- `components/COLOR_AND_SEMANTIC.md` — brand and semantic colors.
- `components/SPACING.md` — layout rhythm and density.
- `components/ICONS.md` — icon hierarchy and contextual use.
- `components/ACCESSIBILITY.md` — focus, labels, states, keyboard behavior.
- `components/RESPONSIVE_AND_HTMX.md` — responsive and partial-update behavior.

## Components

- `components/HERO.md`
- `components/CARD.md`
- `components/TABLE_AND_LABEL.md`
- `components/FORM.md`
- `components/FORM_ACTION_BAR.md`
- `components/CONTEXT_GUIDANCE_CARD.md`
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

## Global guardrail

A local component variant is allowed only when the existing semantic role cannot represent the requirement. The reason and exception must be documented before implementation.
