# KAORI Access Ownership Refactor Audit — 2026-08-08

## Scope

This audit covers structural ownership only. It intentionally does not approve final UI design for User Management, Identity Providers, Roles & Access, Permission Catalog, Activity Audit, or Access Overview.

## Before

- User/provider administration lived under `app/users`.
- RBAC policy lived under `app/rbac`.
- Roles & Access and Permission Catalog HTTP/template ownership still lived under Settings.
- The sidebar already presented all of these as one Access domain.

This produced a navigation/implementation ownership mismatch.

## After

- `app/access/overview` provides the permission-aware Access landing route.
- `app/access/roles` owns role HTTP orchestration, forms, service helper, and presentation context.
- `app/access/permissions` owns Permission Catalog HTTP/presentation.
- Settings retains only redirect compatibility for historical URLs.
- User/provider, authentication, RBAC engine, and Activity Audit source ownership remain in their canonical domains.
- Welcome and breadcrumb navigation resolve through Access ownership.

## Deferred UI review

The following remain explicitly open for individual UI review before Access Final Lock:

- Access Overview
- User Management
- Identity Providers / Directory Provisioning
- Roles & Access
- Permission Catalog
- Activity Audit

No page-specific visual redesign is approved by this structural refactor.
