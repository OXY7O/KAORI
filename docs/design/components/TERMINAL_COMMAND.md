# Terminal Command

Status: **KAORI shared component standard**

`app/templates/components/terminal_command.html` owns the canonical presentation for operator-facing CLI and API commands.

## Contract

- Render commands with `terminal_command.render(...)`; do not rebuild terminal chrome, copy buttons, or copy feedback per page.
- Copy behavior is owned by `app/static/js/clipboard.js` through `data-kaori-copy-*` hooks. Inline handlers and page-local clipboard implementations are not allowed for this component.
- The component works in both the authenticated application shell and the authentication/setup shell; it must not require Alpine or HTMX to copy text.
- `Copy` feedback is temporary, accessible through an `aria-live` label, and returns to the caller-provided label.
- Semantic terminal dots are decoration only. They do not represent command health or execution status.
- Use the dark terminal surface only for executable commands or probes. Explanatory prose remains on normal KAORI surfaces.

## Authentication Setup Reference

`access/authentication/setup_required.html` is the reference unauthenticated consumer. Database bootstrap, manual recovery, and connectivity probes use this shared component so setup instructions retain the same command/copy contract as authenticated operational surfaces.
