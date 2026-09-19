# KAORI Template Structure

## Placement Rules

- `components/`: reusable visual contracts shared by multiple pages or domains.
- `<domain>/<page>.html`: full-page shell and page composition only.
- `<domain>/<page>/partials/`: HTMX fragments and domain-specific sections.
- `layouts/`: application shells only.

A component is promoted to `components/` only when it has a stable parameter
contract and at least two real callers. One-off UI belongs to its domain and must
use a business-specific filename.

## Naming

Prefer:

- `_connection_registry.html`
- `_runtime_diagnostics.html`
- `_inventory_readiness.html`

Avoid ambiguous names:

- `_content.html`
- `_box.html`
- `_misc.html`
- `_new.html`

## Reusable Contracts

Global components own visual implementation for empty states, blockers,
navigation, status badges, pagination, loading indicators, and shared actions.
Domain templates provide data and wording; they do not duplicate those visual
contracts.
