# Numeric Pagination Migration Audit — July 2026

## Scope

The audit covered templates containing Previous/Next controls or legacy current-page indicators across Inventory, Analytics, Integrations, Reports, Governance, Operations, Intelligence, Users, Notifications, Prometheus, and Alertmanager.

## Migration result

Thirty-two server-rendered pagination templates were migrated from `Page x of y`, `x / y`, or single-page badge indicators to the shared `pagination_ui.numeric_pages()` component.

The shared component now provides:

- a maximum five-page numeric window;
- first and last page preservation;
- non-interactive ellipses;
- Violet-soft current-page state;
- neutral clickable numeric pages;
- `aria-current="page"` and page-specific accessible labels;
- HTMX re-initialization after partial swaps.

Client-only Alpine pagination blocks remain governed by the same documented visual contract and should use the shared numeric rendering utility when they are next refactored into reusable components.
