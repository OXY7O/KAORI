# KAORI Notification Center Final Lock v1.2

v1.2 supersedes v1.1. It keeps Notification Center personal and read-only while adding canonical KAORI filtering, explicit Previous/Next pagination, Title Case operational labels, lifecycle/evidence context above the register, and category-aware presentation.

## Notification evidence context

The Notifications tab presents context before the table:

- **Lifecycle Boundary** — persisted inbox records share the Activity Audit retention policy.
- **Delivery Boundary** — transient toasts are immediate UI feedback and are not Data Lifecycle records.
- **Administrative Evidence** — Activity Audit remains the system-wide evidence view.

## Filter contract

The Notification Register uses shared KAORI table/filter/loading primitives and supports:

- Search Notifications
- Category
- Status
- State

Filter changes are HTMX-driven and use the shared loading bar. Auto refresh, row-count changes, mark-read actions, and pagination preserve the active filters.

## Category contract

Canonical categories are:

1. ConfigMap Management
2. TLS Certificate
3. Secret Management
4. Integrations
5. Platform Operations
6. Access
7. Settings

Stored event keys are unchanged; category is presentation/filter metadata.

## Pagination

Default Rows remains 5 with 5/10/25/50 options. Pagination renders **Previous**, numeric pages, and **Next** through shared KAORI pagination classes.

The Notification Register's Rows selector sends a canonical server-backed **GET on change**, rather
than dispatching a second generic `requestSubmit()` event. The request contains the selected
`per_page`, resets `page=1`, and preserves `view=notifications`, search, category, status,
and read-state filters. It swaps only `#activity-notification-page` and pushes the selected
state into browser history. The owning 15-second HTMX refresh and explicit operator Rows change
share a synchronization boundary: an in-flight old poll must not overwrite the newer user
choice. A no-JavaScript `Apply Rows` submit fallback retains native GET behavior.

Do not change the global `data-kaori-auto-submit` controller for this domain-specific request
boundary; other KAORI registries continue to use their existing approved controls.

## Empty-state semantics

Notification Center **page tabs** use the canonical
`components/states/_empty_state.html` component inside their existing owning
surfaces. The component owns icon, semantic status, heading, description, Violet
styling, spacing, responsive layout, and accessible state markup.

- **Active Work with no queued/running or local page operations:** shared panel
  variant, `Queue Clear` (healthy normal tone), and `No Active Work`. Preserve
  `data-running-empty` on the owning wrapper so the existing local-activity
  reconciler hides the panel when work appears and shows it when work completes.
  Job and local-activity sources remain canonical, with no false worker health.
- **Notifications with no account records and no active filter:** neutral
  `No Data` label and `No Notifications Yet`. This is not a delivery error.
- **Notifications with active search/category/status/state filters producing
  zero rows:** `No Results` and `No Matching Notifications` with guidance
  to adjust filters. Keep the separate conditional Clear Filters control.

Keep the Notification Register filter header, 5-row default pagination footer
(including zero counts), HTMX 15-second refresh, account authorization and
committed evidence context visible around the empty component. The navbar's
compact Notification Deck has a different, narrower presentation contract and
is not modified by the page-tab empty-state refinement.

## Copy normalization

Compact Notification titles and event labels render in Title Case while preserving operational acronyms including KAORI, API, ConfigMap, TLS, RBAC, LDAP, OIDC, SSO, SAML, URL, and S3. Visible Kubernetes labels remain fully spelled out. Sentence-style message/detail copy is not title-cased.

## Boundaries

- Notification Center remains user-scoped.
- Activity Audit remains administrative/system-wide.
- Active Work remains a mirror of Jobs & Executions.
- Notification Center does not create or mutate domain resources.
- Operational feedback delivery follows `KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md`.
