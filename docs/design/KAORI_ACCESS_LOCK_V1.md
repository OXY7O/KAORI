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


## Superseding AUTH-UI security mutation scope (#3137)

The earlier AUTH-UI-01 read-only implementation checkpoint is superseded by
reviewable administration on the SAME canonical Access → Authentication
Security page. MFA policy and Bot Protection configuration belong here,
protected by existing `identity_providers.manage` server-side permission
checks, POST + CSRF, committed evidence and the same existing Violet/HTMX
workspace primitives. The default read view remains guarded by
`identity_providers.view`. Bot policy permits Disabled or Always after a
recent live provider verification, with no fabricated health status.
Never place provider verification secrets in HTML or audit.
Adaptive policy remains unavailable until committed risk evaluation exists.
Source changes require Dev Container Visual QA, negative authentication UAT,
human acceptance and existing Access/Settings Final Lock checks.


## Authentication Assurance Overview visual refinement (#3166)

The approved Access → Authentication Security surface retains the **existing** KAORI Hero, workspace tabs, permission guards and MFA/Turnstile/session policy owners. The former generic three-paragraph Overview is superseded by an operational information hierarchy: a source-owned **Authentication Assurance Posture** summary (MFA policy, Turnstile enforcement and generation-based sessions), three **Security Control Summaries** with workspace-tab links, and two **Operational Boundaries** areas explaining what Access governs versus Settings enrollment / Identity Providers.

Statuses MUST derive from committed KAORI MFA and Bot policies; provider adapter registration/configuration alone never proves live vendor health or a user's enrollment. No invented trend/chart/coverage metric or backend mutation is introduced by this visual change. Keep two Hero-context helper sentences compact enough for single-line desktop presentation, but allow natural wrapping on small viewports. Reuse existing Violet semantic colors, border/surface tokens, responsive grids and accessible route-backed links. Do not fork the shared Hero or card macros.

Acceptance requires Dev Container screenshot QA at desktop and mobile in light/dark mode, tab URL/HTMX/accessibility regression checks, exact source SHA, and human review. Official staging/main admission remains HOLD.

## Authentication Assurance Overview visual UAT follow-up (#3166)

Operator screenshot refinement reuses `components/info_tip.html::render(..., variant='guide')` directly beside the **Authentication Assurance Posture** heading. Contextual description moves into the existing accessible hover/focus/click Info Tip rather than a permanent subtitle. The section must not clip the shared popover; its header, posture values and status badge remain visible without opening help.

The **Security Control Summaries** subtitle is removed while all three committed-state controls and existing tab destinations stay unchanged. **Operational Boundaries** now uses balanced, aligned three-row semantic content per column for governed Access controls and related Settings/Identity Provider/security workstream ownership. Preserve the visible scope labels; never move mandatory status/error information into a tooltip.

This change is presentation-only: no authentication admission, policy update, provider verification, database migration, permission or audit logic modification. Review at desktop/mobile and in both themes using the standard Info Tip controller, plus existing Access Final Lock, `djlint` and scoped pytest contracts.


## Authentication Security cards without redundant heading (#3166)

The Authentication Assurance Overview renders the three **MFA, Bot Protection and Session Security** control cards directly after the posture panel. The redundant visible `Security Control Summaries` heading is intentionally omitted at the operator's UAT request. The containing `section` retains an accessible `aria-label="Authentication security controls"` and existing card-level titles, state-derived labels, and navigation. Other workspace tabs, policy controls, and session enforcement remain unchanged. Validate in the normal light/dark and responsive Visual QA workflow.


## Authentication Security sidebar active-state correction (#3181)

Access → Authentication Security is a canonical Level-2 Access capability, not Access → Overview. The shared server-side resolver `app/common/workspace_navigation.py` maps the whole `access.authentication_security.` blueprint endpoint namespace to `authentication_security`, including its Overview/MFA/Bot Protection/Session Security GET view and policy/testing POST routes. Only this Level-2 sidebar child receives the active state for these endpoints; the individual page tabs remain page-owned detail navigation, not a third sidebar level.

Preserve Sidebar Navigation Standard v2.2, permission-aware disclosure, and the existing breadcrumb ownership. Avoid client-side highlight overrides or duplicating active-state logic in the page template. No authentication security runtime/policy/database change is part of this correction.


## MFA policy administration tab review layout (#3189)

`Access → Authentication Security → Multi-Factor Authentication` is a scoped **policy administration** surface; `Settings → Account & Authentication → MFA` remains the user's own TOTP enrollment/recovery surface. This follows the approved KAORI Violet/shared `info_tip.render(variant='guide')`, semantic status labels, responsive grid/card and single `Access` sidebar ownership.

The MFA tab presents a committed policy value (Disabled, Optional, Required Privileged, Required All), method capability (TOTP and single-use recovery), and impact (login/Remember Me generation revocation). It provides one permission-protected `save_mfa_policy` POST with existing CSRF and acknowledgment fields. No new permission taxonomy, authentication route, secret display, adoption estimate, or second policy store is permitted. A viewer has read-only explanatory content; an authorized manager can propose a new mode. Required modes are guarded by the approved enrolled Local Database Super Admin recovery check. A successful policy change invalidates previously issued sessions, including the administrator's current session.

Functional UAT includes live TOTP enrollment in Settings, Disabled/Optional/Required policy transitions, two-browser and recovery-code negatives, accurate Activity Audit and fresh-login issuance. Record exact-SHA automated checks, light/dark/mobile/keyboard Visual QA, and Human Acceptance separately before official admission.


## MFA policy impact and enforcement panel alignment (#3189 UAT follow-up)

The existing Access → Authentication Security → MFA tab uses KAORI's established
warning semantic color tokens (`border-status-warning-border`,
`bg-status-warning-soft`, `text-status-warning-text`) for the
**Change Impact** notice. Keep the copy a single concise sentence:
"Policy changes revoke all sessions; required modes need an enrolled Local Super Admin."
The notice must remain visible beside the existing mandatory acknowledgement;
do not obscure revocation/recovery requirements behind a tooltip.

The **Policy Configuration** and **Enforcement Modes** panels share the
same stretch-aligned grid row at `xl` widths. The left form retains its
authorized/CSRF-protected behavior, while the right policy-mode list grows to
fill the available height with evenly spaced entries. Mobile/smaller
breakpoints stack naturally without fixed heights or horizontal overflow.
No new component, permission, schema, or authentication enforcement
behavior was introduced by this UI adjustment.

The final visual QA checks both columns have aligned top and bottom
edges, warning tone is legible in light/dark mode, the impact sentence
fits naturally at normal desktop widths, and keyboard focus plus Save,
acknowledgement, and Guide remain functional.


## MFA Assurance Policy iconography refinement (#3189 UAT feedback)

The MFA policy administration tab follows the same KAORI Violet iconography
hierarchy already used in the Access workspace. The three committed-state
summary tiles have distinct, **decorative** Lucide cues: shield-check for
Current Policy, key-round for Verification Method, and log-out with the
existing warning-semantic soft surface for Session Impact.

The four enforcement-mode rows use shield-off (Disabled), shield-plus
(Optional), shield-alert (Required Privileged), and shield-check
(Required All); the actual current mode is still determined by
`mfa_policy_mode` and its existing visible text/badge, never icon color alone.
No duplicated text source, new taxonomy, status calculation, or invented
enrollment metrics. Decorative icons must have `aria-hidden="true"`.

Account Enrollment & Recovery retains **personal** enrollment ownership in
Settings and adds compact Authenticator App and Recovery Codes descriptors;
neither is an administrative secret viewer nor a new factor provider.
Keep the existing policy form, acknowledgement, recovery guard, Guide,
session revocation, responsive matched-height panels and light/dark
semantic tokens unchanged. Confirm visual rhythm on narrow screens before
Human Acceptance.

## Bot Protection assurance workspace — approved Visual UAT layout (#3299, 2026-10-26)

The user-approved Bot Protection presentation uses the existing Authentication Security **Overview and MFA Policy** grammar, replacing the former monolithic `Verification Adapters` form without changing the external provider or security engine. Keep shared Hero/tabs, canonical Info Tip Guide, committed-state status badge and three status tiles: **Protection Mode** (Disabled/Always), **Verification Adapter** (admitted Cloudflare Turnstile), and **Provider Configuration** (Configured only if site key, hostname and encrypted secret are all present). Configuration is not a provider-health claim; do not derive a Ready/Healthy badge from `bot_tested_at` without the authoritative freshness/matching check.

Below the posture summary use the same **`xl:grid-cols-5` 3/2 equal-height action/context layout** used by MFA: left **Protection Configuration** contains the existing manager-owned POST form (real `Disabled` / `Always` select, two responsive site-key/hostname controls, one write-only verification secret, fail-closed impact notice, explicit impact acknowledgement and Save); right **Activation & Safety** explains **Configure Provider → Test Verification → Enable Protection** as a non-interactive ordered guide. The only live test control is the existing `test_bot_provider` POST with `cf-turnstile` widget; it appears only for manager permission and a fully saved configuration. Viewers see committed posture and read-only guidance, not a disabled fake action.

**No new provider dropdown, Adaptive mode, suspicious-activity toggle, browser QR scanner, switch control, runtime readiness inference, or new component.** The illustrative design's Enabled badge/toggle does not supersede the committed policy or the available server modes. The existing Siteverify kernel remains authoritative: one-use verified token, `login` action/hostname binding, proof for the unchanged configuration within one hour, default Disabled, server fail-closed on rejection/unavailability, encrypted secret, sanitized audit and protected recovery operations. Error feedback remains on the current server endpoint; not a new client-only save or test state.

Desktop 1440/1280/1159, tablet 768, mobile 390/360, both light/dark, keyboard focus and contrast must be visually verified without horizontal overflow; meaningful configured/unconfigured and manager/read-only states must be examined. Use existing `ruff`, `djlint`, `pytest`, Access Final Lock, sidebar, Visual QA, DAST/security and human acceptance. Source checks alone do not establish safe provider activation. Official admission remains HOLD.
