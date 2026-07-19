# Pagination Audit — July 2026

## Scope

The audit reviewed pagination-related templates and normalization helpers across Kubernetes inventory, analytics, integrations, governance, operations, reports, notifications, settings, users, and shared presentation services.

## Standard established

- Default page size is `5`.
- Allowed page sizes are `5`, `10`, `25`, and `50`.
- Summary text follows `Showing {start}–{end} of {total} {resource}`.
- Empty states use `Showing 0–0 of 0 {resource}`.
- Resource names are explicit and use correct singular/plural wording.

## Corrections included in this patch

- Changed shared analytics pagination defaults from `10` to `5`.
- Changed the workload pagination fallback from `10` to `5`.
- Added the missing `integration target(s)` resource label to Integrations Overview.
- Replaced the Users footer wording `Viewing ... matching user accounts` with the global `Showing ... users` contract.
- Normalized inventory resource wording to lowercase sentence style.
- Normalized pagination range separators to an en dash in reviewed templates.
- Stabilized the shared Alerts and Anomalies empty summary at `0–0 of 0` instead of replacing the footer with an unrelated empty sentence.
- Added a visible `Rows per page` label to the shared Alerts and Anomalies pagination component.

## Existing compliant areas

The reviewed inventory tables, Alertmanager and Prometheus histories, TLS governance tables, Secret Reveal tables, roles, permissions, notifications archives, workload mappings, and report-type lists already identify the counted resource in their summary.

## Follow-up migration boundary

Several legacy footers still use a `Page X of Y` indicator instead of numeric page buttons. They remain functionally valid but are classified as a visual migration backlog. The global standard for new and redesigned tables is Previous, bounded numeric page controls, and Next. This backlog must be migrated component-by-component rather than by unsafe global markup replacement because URL and HTMX state differ by module.

Dashboard-only snapshots with a fixed bounded limit are treated as approved exceptions and do not redefine the table pagination standard.
