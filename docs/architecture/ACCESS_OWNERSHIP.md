# KAORI Access Ownership Baseline v1.1

Status: **Final Locked — Access v1**

## Objective

Access is one administrative control plane in navigation while implementation ownership remains explicit and maintainable.

```text
Access
├── Overview                 app/access/overview
├── User Management          app/users
├── Identity Providers       app/identity_providers + app/auth/identity_provider
├── Roles & Access           app/access/roles + app/rbac
├── Permission Catalog       app/access/permissions + app/rbac
└── Activity Audit           app/access/activity_audit + app/notifications evidence store
```

## Structural decisions

1. Settings no longer owns role or Permission Catalog presentation/mutation logic.
2. `app/access/roles` owns role HTTP orchestration, forms, and presentation helpers.
3. `app/access/permissions` owns the read-only Permission Catalog HTTP/presentation boundary.
4. `app/rbac` remains the authorization engine and code-owned permission/default-role authority.
5. `app/users` remains the user lifecycle domain.
6. `app/identity_providers` owns Identity Provider administration while `app/auth/identity_provider` owns protocol/authentication adapters.
7. `app/access/activity_audit` owns Activity Audit HTTP/presentation; `app/notifications` owns the shared immutable operational evidence store/query kernel.
8. Old `/settings/roles*` and `/settings/permissions` URLs are retired; Access has no Settings compatibility shim.
9. Access Overview is read-only and permission-aware.
10. Access child-page UI is final-locked under `docs/design/KAORI_ACCESS_LOCK_V1.md` and protected by `scripts/verify_access_final_lock.py`.
