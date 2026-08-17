# KAORI Access Final Lock v1

Status: **FINAL LOCKED**

## Scope

Access Final Lock v1 covers:

- Access Overview;
- User Management;
- Identity Providers and LDAP Directory Provisioning;
- Roles & Access;
- Permission Catalog;
- Activity Audit.

Runtime ownership remains explicit: `app/users` owns account/provider administration, `app/auth` owns authentication/session admission, `app/rbac` owns authorization policy, and `app/notifications` owns Activity Audit persistence/presentation. `app/access` is the control-plane composition owner.

## Locked security boundaries

1. Access Overview is read-only and permission-aware.
2. Roles require `roles.view` for reads and `roles.manage` for mutations; protected default roles remain code-owned. Custom-role writes use row locking plus a role-version token.
3. Permission Catalog is read-only under `roles.view`; HTTP GET paths never seed or converge RBAC state.
4. User Management uses explicit `users.*` permissions, protects administrator-level accounts, and serializes last-active-super-admin disable/demotion/delete decisions.
5. Password replacement advances `User.auth_session_version`; existing sessions and remember cookies fail closed on the next request.
6. Remember-me persistence defaults to 7 days and is bounded to 1–30 days. Super-admin remember-me remains default-deny.
7. Identity Provider administration requires `users.manage`; provider records keep secret values externalized and runtime validation remains on-demand.
8. Failed authentication attempts may remain linked to a target account for evidence, but never claim that target as the authenticated actor. Activity filters and 24-hour actor counts exclude failed-authentication targets.
9. Activity Audit requires `activity_audit.view` and remains read-only administrative evidence.

## Locked presentation boundaries

- KAORI Violet and semantic token classes only; no raw palette/hex drift.
- Shared Hero, tables, labels, pagination, loading bar, framed tabs, detail modal, destructive confirmation, toast, and right-rail patterns remain canonical.
- Rows default to the shared 5/10/25/50 pagination contract where paginated registries apply.
- Visible labels remain Title Case; arbitrary typography and template-local inline UI debt are forbidden.
- Permission detail uses the shared content-driven modal; dynamic Tailwind arbitrary-value classes must remain token-contiguous and are formatter-protected.
- Notification deck runtime behavior remains owned by syntax-checked `app/static/js/navbar.js`, not inline navbar JavaScript.

## Legacy cleanup

- `/settings/roles*` and `/settings/permissions` are retired.
- No Settings compatibility shim or role/permission wrapper may return.
- `role_access_tabs.js` remains removed.

## Release evidence

The permanent release guard is `scripts/verify_access_final_lock.py`, with contract coverage under `tests/contracts/access`, `tests/contracts/auth`, and the Activity Audit/Notification Center contracts.
