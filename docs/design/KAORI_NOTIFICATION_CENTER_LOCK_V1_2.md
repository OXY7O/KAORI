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

## Copy normalization

Compact Notification titles and event labels render in Title Case while preserving operational acronyms including KAORI, API, ConfigMap, TLS, RBAC, LDAP, OIDC, SSO, SAML, URL, and S3. Visible Kubernetes labels remain fully spelled out. Sentence-style message/detail copy is not title-cased.

## Boundaries

- Notification Center remains user-scoped.
- Activity Audit remains administrative/system-wide.
- Active Work remains a mirror of Jobs & Executions.
- Notification Center does not create or mutate domain resources.
- Operational feedback delivery follows `KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md`.
