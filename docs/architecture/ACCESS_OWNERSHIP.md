# KAORI Access Ownership Baseline v1.1

Status: **Architecture baseline — UI not final locked**

## Objective

Access is one administrative control plane in navigation while implementation ownership remains explicit and maintainable.

```text
Access
├── Overview                 app/access/overview
├── User Management          app/users
├── Identity Providers       app/users + app/auth provider adapters
├── Roles & Access           app/access/roles + app/rbac
├── Permission Catalog       app/access/permissions + app/rbac
└── Activity Audit           app/notifications
```

## Structural decisions

1. Settings no longer owns role or Permission Catalog presentation/mutation logic.
2. `app/access/roles` owns role HTTP orchestration, forms, and presentation helpers.
3. `app/access/permissions` owns the read-only Permission Catalog HTTP/presentation boundary.
4. `app/rbac` remains the authorization engine and code-owned permission/default-role authority.
5. `app/users` remains the user lifecycle and provider-administration domain.
6. `app/auth` remains the protocol/authentication boundary.
7. `app/notifications` remains the Activity Audit evidence owner.
8. Old `/settings/roles*` and `/settings/permissions` URLs are retired; Access has no Settings compatibility shim.
9. Access Overview is read-only and permission-aware.
10. Child-page UI is intentionally not final-locked until page-by-page review is complete.
