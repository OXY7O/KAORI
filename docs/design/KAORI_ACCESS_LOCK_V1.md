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

Runtime ownership remains explicit: `app/access/users` owns account lifecycle, `app/access/identity_providers` owns provider administration, `app/access/authentication` owns authentication/session admission, `app/access/rbac` owns authorization policy, `app/access/activity_audit` owns the Activity Audit workspace, and `app/platform_operations/notifications` owns its shared operational evidence store/query kernel. `app/access` is the control-plane composition owner.

## Locked security boundaries

1. Access Overview is read-only and permission-aware.
2. Roles require `roles.view` for reads and `roles.manage` for mutations; protected default roles remain code-owned. Custom-role writes use row locking plus a role-version token.
3. Permission Catalog is read-only under `roles.view`; HTTP GET paths never seed or converge RBAC state.
4. User Management uses explicit `users.*` permissions, protects administrator-level accounts, and serializes last-active-super-admin disable/demotion/delete decisions.
5. Password replacement advances `User.auth_session_version`; existing sessions and remember cookies fail closed on the next request.
6. Remember-me persistence defaults to 7 days and is bounded to 1–30 days. Super-admin remember-me remains default-deny.
7. Identity Provider reads, mutation, and directory projection use the dedicated `identity_providers.view/manage/provision` permission family; provider records keep secret values externalized and runtime validation remains on-demand.
8. Failed authentication attempts may remain linked to a target account for evidence, but never claim that target as the authenticated actor. Activity actor identity is snapshotted separately from the notification recipient.
9. Activity Audit requires `activity_audit.view` and remains read-only. Its default **Activity Register** tab reads hot PostgreSQL `notifications` evidence (including audit-only records), linking older verified evidence to Data Lifecycle archive history. A separate, source-permissioned **Administrative Evidence** tab can inspect explicitly allowlisted hot `AuditEvent` sources without combining rows, actor identity, counts or retention. Actor FK references in `AuditEvent` are not immutable snapshots, and their archive continuity is not implied. The system-wide read permission does not grant access to domain-owned `audit_events`, `tenant_audit_evidence` or JobExecution without source permissions. User deletion cannot cascade-delete Activity Register evidence.

## Locked presentation boundaries

- KAORI Violet and semantic token classes only; no raw palette/hex drift.
- Shared Hero, tables, labels, pagination, loading bar, framed tabs, detail modal, destructive confirmation, toast, and right-rail patterns remain canonical.
- Rows default to the shared 5/10/25/50 pagination contract where paginated registries apply.
- Visible labels remain Title Case; arbitrary typography and template-local inline UI debt are forbidden.
- **UAT-1(3) #1335:** Identity Governance descriptions should remain concise on 14-inch laptop layouts with sidebar open, while preserving provider, adapter, secret, projection and KAORI authorization boundaries. Do not force single-line display through nowrap or clipping; mobile and zoom may wrap.
- **Access UAT-1(2) layout refinement (#2257):** Access Overview `Access Boundaries` uses the existing external `section_intro.render` heading/description above an accessible `operational_section.shell_classes()` boundary-card shell, paralleling Roles' Authorization Flow section. No duplicated card-internal heading; permission-scoped boundary cards, statuses, conditional display, and responsive grid remain unchanged.
- **User Lifecycle & Administrative Controls UAT-1(1) (#2253):** the three existing form controls (Assigned Role, Active Account, protected Super Admin) share the established violet card header geometry with concise explanatory text below, never replacing their distinct source-backed role/select, activation or privileged eligibility semantics. The conditional Super Admin unavailable state remains explicit; last-active-local-Super-Admin and self-edit safeguards stay authoritative. No new UI primitive or role permission path.
- **Access UAT-1(1) result badges (#2252):** Permission Registry, Role Coverage and Administrative Source Evidence share the existing `table_label.result_count` badge immediately beside their card header titles. The count is derived from current filtered registry or evidence pagination; the other header actions remain right-aligned. Framed navigation tabs remain unbadged as approved by #1247.
- **Access UAT-1(1) copy refinement (#2251, 2026-10-17):** responsive evidence, authorization and role helper descriptions use concise desktop-friendly statements without `nowrap`, clipping or hidden details. This supersedes previously locked *literal helper wording* only; the shared Role Detail `resource_sheet`/`inventory_section` layout, source-owned RBAC delegation, inactive-role fail-closed behavior, Notification-backed hot Activity Audit, verified Data Lifecycle archive, and Local Database Super Admin protections remain unchanged. Mobile/zoom copy may wrap naturally; visual acceptance is still pending.
- Permission detail uses the shared content-driven modal; dynamic Tailwind arbitrary-value classes must remain token-contiguous and are formatter-protected.
- Notification deck runtime behavior remains owned by syntax-checked `app/static/js/navbar.js`, not inline navbar JavaScript.

## Legacy cleanup

- `/settings/roles*` and `/settings/permissions` are retired.
- No Settings compatibility shim or role/permission wrapper may return.
- `role_access_tabs.js` remains removed.

## Release evidence

The permanent release guard is `scripts/verify_access_final_lock.py`, with contract coverage under `tests/contracts/access`, `tests/contracts/auth`, and the Activity Audit/Notification Center contracts.


Activity Audit administrative presentation uses existing framed workspace navigation and shared table registry behavior (full-width filters, Clear Filters, loading, Rows 5/10/25/50, numeric pagination, empty state), restricted to allowed hot AuditEvent sources and their existing domain permissions. This does not expand actor snapshots or archive authority.
