# Kubernetes ConfigMap and Secret Operations Styling Audit — July 2026

## Scope

Reviewed:

- ConfigMap and Secret operation landing pages;
- Create, Update/Replace, and Delete workspaces;
- Protected Secret Reveal;
- single and bulk TLS rotation;
- shared operation components and validation controllers;
- Inventory modal relationship queries and technical text wrapping reported during the same review.

## Findings before remediation

- workflow catalogs used fixed-height cards and repeated guardrail copy;
- permission state and operation classification were mixed;
- local operation components duplicated global action, rail, and form geometry;
- form controls retained the old 44 px standard;
- Protected Reveal displayed request, registry, approvals, and one-time output in one competing layout;
- delete workflows lacked a final KAORI confirmation modal;
- Reveal and bulk TLS numeric pagination did not fully own their HTMX target and query state;
- PostgreSQL generic JSON columns were queried with `.contains()` that compiled to `LIKE`, causing `operator does not exist: json ~~ text` for Service and Storage details;
- long Kubernetes label, annotation, host, selector, and template values were constrained by narrow columns or truncation in Full Workspace Modal.

## Decisions applied

- Operational Workflow Catalog and Operational Workflow Card;
- Live Mutation Evidence Contract;
- canonical context rail and form action bar;
- Structured Entry Editor;
- Operational Choice Card Group;
- Protected Reveal segmented workspace;
- Protected Value Panel;
- final destructive confirmation modal;
- `No KAORI Value Persistence` wording;
- scoped registry and TLS pagination;
- PostgreSQL `CAST(... AS JSONB) @>` containment with non-PostgreSQL fallback;
- 100 rem Inventory modal, overflow-safe detail rows, and readable technical metadata columns.

## Security boundaries retained

- live Kubernetes remains mutation authority;
- Inventory remains best-effort impact context;
- server-side dry-run and final revalidation remain mandatory;
- delete receipts remain actor-, session-, target-, and resourceVersion-bound;
- Secret replacement never renders existing values;
- Protected Reveal remains permission-, policy-, approval-, and step-up-gated;
- one-time values remain absent from persistent notifications and Activity Audit payloads.

## Result

The operation pages now use one coherent KAORI operations language while preserving domain-specific security controls. Inventory modal evidence no longer fails on PostgreSQL JSON comparison and no longer intentionally truncates long technical strings.
