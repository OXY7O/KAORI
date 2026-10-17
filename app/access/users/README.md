# User Management

`app/access/users` owns KAORI user lifecycle and effective-access presentation. It does not authenticate credentials, configure external identity providers, or implement provider protocols.

## Ownership

- `directory.py`: read-side user directory, filtering, pagination, identity context, and Effective Access presentation.
- `service.py`: user mutations, lifecycle guardrails, and Local Database break-glass enforcement.
- `access_summary.py`: source summary consumed by Access Overview.
- `forms.py`: Local Database user lifecycle forms.

External Identity Provider administration is owned by `app/access/identity_providers/`. Authentication protocol and adapter behavior is owned by `app/access/authentication/identity_provider/`. RBAC policy remains owned by Access Roles/Permissions.

## Identity and access boundary

Canonical user sources are provider keys from the Identity Provider catalog. UI grouping uses provider families (`database`, `directory`, `sso`) rather than product names.

- Local Database owns KAORI password credentials and is the only valid Super Admin break-glass source.
- Directory providers own external credentials; KAORI stores identity projection and authorization state only.
- Browser SSO providers own external authentication; KAORI stores the external subject link, lifecycle state, and RBAC role.
- Missing role, inactive role, missing/disabled external provider, invalid identity link, inactive account, or invalid external Super Admin state fail closed and surface as Effective Access findings.

## Break-glass invariant

`is_super_admin` is valid only when `auth_source == 'database'`. At least one active Local Database Super Admin must remain available. External Directory/SSO identities may receive normal RBAC roles but never the break-glass flag.

## Extension rule

Adding a new Identity Provider must not add provider-specific branching to User Management. `app/access/users` consumes only catalog-derived provider identity/family and identity-link state.

## Shared Administrative Audit Boundary

User, Role, and Identity Provider mutations write the persisted `AuditEvent` ledger through `app/common/admin_audit.py`. User Management does not own that helper; each Access administration workspace records audit evidence in the same transaction as its mutation. Notification-backed Activity Audit feedback remains a separate operator-facing evidence stream.

## Password Reset Session Boundary

Local password changes and administrator resets advance `User.auth_session_version` to revoke all existing authenticated sessions and remembered sign-ins for the affected credential generation. Self-service change may re-establish only the current browser on the new generation.


### UAT-1(6) User Detail heading badges — #2265

The existing five-band User Detail resource sheet adds source-backed badges to the Identity, Authentication and Authorization left header descriptions. Identity uses the recorded source label; Authentication uses actual credential ownership; Authorization uses computed effective access with semantic status color. These reuse the shared inventory-section macro without new markup or permission changes. The rendered Firefox/sidebar-open review and human acceptance remain pending.


### UAT-1(6) User Edit copy-density follow-up — #2253

Keep the longer Local Database credential-boundary explanation grounded in `build_user_identity_context`, but show a short one-line local credential caption within the narrower violet Current Identity Source card. The User Registry related-page summary/boundary and administrative-control steps 01–02 now use fuller, balanced two-line descriptions at the operator's Firefox L13 viewport. Directory/SSO ownership and authorization guards remain unchanged. Browser line counts, mobile wrapping, Jinja/pytest and human acceptance remain pending.

### Reset Password copy-density UAT — #2273

The Reset Password page retains provider-owned credential boundaries and the
`User.auth_session_version` revocation model. The security warning, password
helper, Local Database/Directory ownership guidance, Target Account RBAC note
and Reset Impact session hint use concise, factual captions. Firefox Lenovo L13
operator feedback targets one desktop line for four captions and two desktop
lines for Directory Provider and RBAC preservation. This is a copy-only change:
no `whitespace-nowrap`, truncation, smaller fonts, altered reset policy or
external-provider password actions. At narrow viewports and increased browser
zoom, text must wrap naturally. Targeted source-contract checks and actual
Dev Container Firefox screenshots/human acceptance are separate evidence;
the latter remain PENDING until executed.

### REVIEW(2) — Add User Guide and User deletion confirmation (#2278)

The Add User credential section now places minimum password length, passphrase
uniqueness and exact confirmation advice inside the existing accessible title-level
Info Tip Guide. The two static helper sentences below the credential inputs are
removed without altering placeholders, server-side password policy, validation errors,
CSRF, Directory/SSO ownership or the edit-mode identity projection. The
administrative audit caption and related Identity Providers summary are shortened.
The Delete User confirmation describes login disablement, retained Activity Audit
and Restore → Inactive with separate activation; destructive safeguards remain
unchanged. These are Firefox Lenovo L13 copy targets, not browser PASS until
executed and accepted in Dev Container; mobile and zoom must wrap naturally.

### REVIEW(2) follow-up — User Registry and self-edit notice (#2278)

Firefox L13 review further requests one-line-friendly User Registry navigation
and Local Database ownership summaries, as well as the self-edit warning and
the Delete User confirmation notice. The existing `info_tip` title-level
Guide on **Editing Your Own Profile** preserves the complete prohibition on
changing one's own role, active state and Super Admin flag while the visible
caption stays short. The modal retains the login disablement, audit retention
and Restore → Inactive plus separate activation explanation. No server-side
self-edit, CSRF, protected-admin or deletion guard changed. Browser rendering
and accessibility acceptance remain pending at the exact aggregation SHA.
