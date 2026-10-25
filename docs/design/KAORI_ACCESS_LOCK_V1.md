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
- **User Management UAT-1(4) copy (#2253):** remove redundant Display Name default and Assigned Role post-login helper lines while retaining role select/conditional admin-delegation safeguard; compact create-password and provider/authorization guides for the laptop side rail. RBAC, external credentials/JIT, minimum password length and last-active-Local-Super-Admin protections remain enforced in existing validation/server logic. Mobile natural wrapping; human acceptance pending.
- **Access UAT-1(4) modal chrome (#2261):** Permission/Role/Activity details already use the shared resource-detail header/footer authority. Only Access destructive confirmations opt into matching surface-card header/footer, top-right close control and scoped footer context; destructive action/Cancel semantics remain distinct. Body, width, data attributes and default shared behavior in other domains must remain untouched. Visual/keyboard human acceptance pending.
- **Superseding UAT-1(5) screenshot clarification (#2261):** the provided image shows the **Permission Detail header for `users.delete`** (`Delete Users`, `Canonical`, description and Access/key/delegation badges), not a destructive User deletion prompt. Use its *structure* as the Access modal header authority: icon, title + applicable semantic status, description, then source-backed metadata badges; Role/Activity detail reorders their existing fields to match, while Access-only destructive confirmation uses a truthful `Confirmation Required` warning badge and scope/action metadata. The shared Resource Detail footer remains authoritative because the screenshot does **not** depict any footer. Preserve each modal's body/width, close/confirm semantics, RBAC and non-Access default style. Browser/keyboard/human UAT pending.
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

- **User Detail UAT-1(6) (#2265):** Identity, Authentication and Authorization left-hand resource-sheet headings use the existing shared `inventory_section` badge below description on xl desktop (near title at smaller widths), bound respectively to identity-source label, credential owner and effective KAORI access status/tone. Do not invent static trust/permission status, change the fact grid, provider authority, lifecycle or mutation gates. Firefox L13 and responsive human UAT pending.
- **User Edit copy UAT-1(6) (#2253):** local password-hash/reset ownership remains in the canonical user identity read model; the credential boundary explanation stays informative (roughly two laptop lines), while the narrow violet Current Identity Source caption uses a separate one-line-friendly local label. Related User Registry summary/boundary and editable administrative steps 01–02 use balanced two-line copy. This does not change upstream provider authority, RBAC, password-reset service, lifecycle or URLs. No forced nowrap or clipping; actual Firefox Lenovo L13 line count and human acceptance pending.

## Activity Audit — Shared Register Hover Guidance (#2885, 2026-10-23)

Explicit authority for this title-level placement is
`docs/design/components/INFO_TIP.md` and
`docs/design/components/TABLE_AND_LABEL.md` (Guide next to title);
the previous Access-specific wording prescribing icon-only help was
incorrect and is superseded. Add these consumers to the existing Guide
design regression list to prevent repeating the error.

The operator accepts Activity Audit functional UAT, with a bounded
follow-up for read-only hover help on **Activity Register** and
**Administrative Source Evidence**. Extend the existing section-card
title/count flex row with one canonical compact Violet
`components/info_tip.html::render(..., variant='guide')` title-level
trigger **directly after each owning heading and before result-count**.
The tiny icon-only `circle-help` variant is field/row guidance only.
This corrects the former title-level UAT conformance error (#2885), not
the established global Info Tip standard from #1680/#2416.
Unique tooltip IDs, keyboard/focus/touch access, native shared Info Tip
portal and responsive viewport clamp are required. Do **not** introduce
a page-local tooltip implementation or shift approved header actions.

Activity Register guidance qualifies committed *Notification-backed hot*
operational and audit-only evidence and immutable actor snapshots.
Administrative guidance qualifies separate authorized hot `AuditEvent`
source projections, actor FK non-snapshot behavior, and Source-owned/Job
links; Archive History is **bundle-level**, not a per-job match claim.
Framed tabs, scoped result counts, read-only modal, source permissions,
GET/HTMX filters and archive ownership are unchanged. Visual QA for
hover/focus, screen-reader trigger naming, mobile, zoom and light/dark
remains a separate DevContainer acceptance gate.

## Authentication Security extension (AUTH-UI-01 / #3138)

A bounded, read-only **Access → Authentication Security** workspace is added after Identity Providers without replacing the final-locked Access navigation, RBAC or UI primitives. It uses the existing KAORI Violet Hero, query-backed `workspace_tabs.render_query_tabs`, server-owned GET/HTMX partial, `identity_providers.view` read access, and standard tabs for Overview, Multi-Factor Authentication, Bot Protection and Session Security.

**Source-only readiness** is never misrepresented as enabled security posture: the MFA policy kernel (#3133) is not an enrolled/verified second-factor challenge; the Turnstile verification kernel (#3136) is not a registered provider instance or an enforced browser login challenge. No admin enable toggles, client secret handling, new login runtime, new RBAC permissions, or new provider catalog are activated through this read-only page.

Future MFA self-service belongs to Settings → Account & Authentication (#562/#3134); controlled provider instance and policy administration under this Access capability remain blocked by #3137 until admission and operator UAT. Preserve canonical responsive/light-dark/a11y/loading, scoped permission checks and progressive navigation.


## Authentication Security functional policy extension (#3134 / #3137)

The prior #3138 *read-only preview* is superseded only for admitted authentication-security sub-capabilities after schema migration and operator acceptance: Access → Authentication Security uses the existing permission-gated workspace with admin mutations under `identity_providers.manage`, while reads still require `identity_providers.view`. The shared Hero, query-backed HTMX tabs, status components, responsive and accessibility standards remain authoritative.

MFA admin mode (Disabled/Optional/Required Privileged/Required All) and provider-specific Bot Protection mode (Disabled/Always initially) are persisted policy, **not** a new primary Identity Provider. All state changes require CSRF and committed audit; activation revokes previously issued sessions as governed. Cloudflare Turnstile site key and hostname are public management fields, but verification secret is encrypted, never echoed. Unknown/invalid provider configuration fails closed; source-only registration is not live readiness. Adaptive/hCaptcha are not labeled ready.

The authorization boundary stays server-owned and permission-scoped. The controlled user self-service factor belongs to Settings → Account & Authentication, not Access; user-factor recovery/reset requires proof or operator-shell incident procedure. Successful challenge verification, audit correlation, and first-login mandatory enrollment are subject to real Dev Container Human Acceptance.
