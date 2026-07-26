# TLS Certificate Governance

## Purpose

This module owns certificate discovery, inventory presentation, expiry and risk posture, Subject Alternative Name coverage, issuer metadata, and Ingress relationships.

## Boundary

Governance is read-oriented. It identifies certificate posture and directs users to a controlled operation when a certificate must be rotated. Kubernetes Secret mutation workflows are owned by `app/kubernetes_operations/secrets`.

Governance may:

- collect TLS Secret certificate metadata;
- calculate expiry and risk status;
- present SAN and Ingress relationships;
- synchronize the certificate inventory snapshot;
- link to a Secret Management operation.

Governance must not:

- persist uploaded private keys;
- own create, update, or rotation forms;
- patch Kubernetes Secrets directly from its presentation routes;
- grant mutation access through a read permission.

## Shared validation

X.509 parsing and certificate/private-key matching live in `app/kubernetes/secrets/tls.py`. The compatibility module `validator.py` remains temporarily for existing imports.

## UI boundary

The Kubernetes TLS Secret governance UI follows the KAORI violet design standard across overview, detail, and bulk update pages. Structural surfaces and actions use KAORI brand tokens; certificate validity and expiry states remain semantic. Gradients and decorative blue/cyan treatments are not used. Governance remains read-oriented posture and relationship context, while certificate/private-key mutation is executed through the controlled Kubernetes Operations TLS rotation workflow.

## KAORI presentation and workflow contract

- TLS certificate inventory, detail, and rotation entry points use neutral structural surfaces with semantic status colors reserved for healthy, warning, critical, expired, and invalid states.
- Inventory actions use the shared expandable-row behavior in `components/details/_expandable_row.html` and `app/static/js/detail_rows.js`; TLS tables do not maintain a separate inline toggle implementation.
- Page-size selectors use the global `data-kaori-auto-submit` behavior. Manual Sync TLS does not create a separate request-progress toast; the worker state is shown in the inventory summary and the dispatch result uses the canonical operational feedback toast.
- TLS inventory and certificate-detail heroes use the canonical `page_hero.context_card()` posture panel with a semantic status, two certificate metrics, and one contextual CTA. Sync and bulk-update mutations remain in the content toolbar; the hero CTA only navigates to the relevant workspace.
- Governance remains read-oriented. Bulk and single TLS Secret mutation actions link to Secret Management, and obsolete Governance-owned mutation templates are not retained.
- TLS Governance does not use Flask flash messages; missing-record and cluster-setup feedback use the KAORI notification and Activity Log pipeline.

## Automatic TLS Certificate Inventory Synchronization

TLS certificate inventory is owned by the canonical registered job `governance.tls_certificates.sync`.
The definition runs on the existing `inventory` queue and is enabled by default with a six-hour interval.
Celery Beat only claims due `job_policies`; the inventory worker performs Kubernetes API collection and
commits each cluster independently.

Supported triggers:

- scheduled fleet collection from the database-backed job policy;
- manual fleet or selected-cluster enqueue from Kubernetes TLS Secret;
- manual fleet execution from Jobs → Configure Jobs;
- selected-cluster recovery collection when a Kubernetes integration transitions back to healthy.

The web route must never call Kubernetes Secret collection inline. Manual Sync TLS only dispatches or
joins a canonical `JobExecution`. Active execution, last successful collection, next scheduled run, and
freshness are presented from `JobExecution`, `JobPolicy`, and committed `TLSCertificateInventory` rows.
A successful collection with zero TLS Secrets still establishes freshness through the terminal job record.

## Worker Registration And Recovery

The TLS synchronization task module must be present in `Config.CELERY['imports']`, and the canonical task name must have an explicit route to the `inventory` queue. This is required even though web routes import the dispatch adapter: worker processes build an independent task registry at startup.

After deploying a task-registration change, rebuild or restart the inventory worker. A message previously rejected as an unregistered task has already been discarded by Celery and cannot resume automatically. Cancel the corresponding queued execution in Jobs & Executions, then dispatch a new TLS synchronization after the updated worker reports the task as registered.

## Inventory Filter And Polling Contract

The synchronization panel, summary, filters, table, and pagination share the `tls-certificates-inventory-scope` HTMX boundary. Active synchronization polling replaces that same scope using its current Cluster, Namespace, Status, Search, Page, and Rows Per Page values. Filter changes also replace the same scope. Polling must never be attached to the outer page container while filters replace only the table, because an older polling URL would restore default filter values.

The TLS Secret table uses the shared Inventory presentation macros in `components/table.html` for block geometry, loading state, filter controls, table headers and rows, Cluster identity, Namespace identity, and pagination geometry. Semantic certificate status labels remain text-only.

## Inventory Summary Presentation

The content before the TLS Secret table follows the canonical Kubernetes Inventory structure. The page renders one shared inventory summary surface containing the summary header, four primary metrics, healthy coverage, synchronization state, next schedule, and the TLS inventory action bar. `inventory/components/_summary.html` remains the source of truth for summary header, metric, progress, and status presentation. The TLS-specific action bar is nested inside the same summary surface so the page does not introduce a separate oversized synchronization card before the table.

Healthy Coverage, Synchronization, and Next Scheduled use one fixed three-column row inside the summary surface. They must not fall into separate rows at desktop inventory widths; all three cards use an equal-width allocation so the row remains visually balanced.

The order is fixed as:

1. canonical page hero;
2. certificate inventory summary and operations;
3. canonical Inventory table block.

Active synchronization progress stays inside the inventory summary surface. Filter, pagination, synchronization, and polling continue to replace `tls-certificates-inventory-scope`, preserving the current filter state.

## Inventory Presentation Dependencies

- The pre-table posture surface reuses `app/templates/inventory/components/_summary.html`. Replacement packages that change the TLS inventory summary must include this canonical component so a partially upgraded deployment cannot fail with `TemplateNotFound`.
- TLS pagination uses the canonical `components/pagination.html` controls and the global `app/static/js/pagination.js` numeric-page renderer. Full-page `href` values remain navigable while `hx-get` requests replace the current TLS inventory scope and preserve active filters.
- The retired page-specific script `app/static/js/tls_certificate_management.js` must not be restored. Its request toast was not lifecycle-bound to the HTMX request and could remain visible after the worker job completed.
