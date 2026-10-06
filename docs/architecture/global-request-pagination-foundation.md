# Global Request and Pagination Foundation

## Decision

KAORI uses canonical helpers for cross-domain HTTP request detection and table pagination:

- `app.common.http` owns HTMX request and target detection.
- `app.common.pagination` owns positive integer parsing, approved page-size choices, and zero-safe pagination windows.

Route and presentation modules must not create new local `_is_htmx_request`, page parser, or `[5, 10, 25, 50]` constants.

## Behavioral contract

- HTMX is active only when `HX-Request` explicitly resolves to `true`, case-insensitively.
- The default page size is 5.
- Allowed interactive table sizes are 5, 10, 25, and 50.
- Invalid page sizes fall back to 5.
- Page values are positive and clamped to the available range.
- Empty collections render `Showing 0–0 of 0` semantics.
- A pagination window always reports at least one logical page so templates do not divide by zero or generate page 0 links.

## Initial migrations

The first migration covers Prometheus, Alertmanager, integration binding routes, User Management, and Report Templates. Other domains retain their existing behavior until migrated in their own audited domain batch.

## Validation and rollback

Functional tests live under `tests/common/`. Architecture checks should reject new local HTMX detector functions and duplicated global page-size constants after all domains are migrated.

Rollback consists of restoring the affected consumer calculations while leaving the canonical helpers available; no database or migration rollback is required.
