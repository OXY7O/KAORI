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


## Compact Density

Use `compact=true` when the command belongs to a dense setup, recovery, or supporting workspace where the default command chrome would create unnecessary vertical weight.

Compact mode keeps the same dark terminal surface, copy runtime, accessible feedback, monospace command text, and semantic dots while reducing only chrome density:

- terminal header: 6 px vertical padding;
- command body: 8 px vertical padding;
- copy control: 24 px minimum height;
- terminal dots: 6 px;
- command text remains 12 px and never shrinks below the KAORI readable minimum.

The default density remains authoritative for ordinary operator command blocks. Do not reproduce compact terminal classes in page templates.

## Authentication Setup Reference

`access/authentication/setup_required.html` is the reference unauthenticated consumer. Database bootstrap, manual recovery, and connectivity probes use this shared component so setup instructions retain the same command/copy contract as authenticated operational surfaces.
