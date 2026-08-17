# User Management

`app/users` owns KAORI user lifecycle and effective-access presentation. It does not authenticate credentials, configure external identity providers, or implement provider protocols.

## Ownership

- `directory.py`: read-side user directory, filtering, pagination, identity context, and Effective Access presentation.
- `service.py`: user mutations, lifecycle guardrails, Local Database break-glass enforcement, and administrative audit events.
- `access_summary.py`: source summary consumed by Access Overview.
- `forms.py`: Local Database user lifecycle forms.

External Identity Provider administration is owned by `app/identity_providers/`. Authentication protocol and adapter behavior is owned by `app/auth/identity_provider/`. RBAC policy remains owned by Access Roles/Permissions.

## Identity and access boundary

Canonical user sources are provider keys from the Identity Provider catalog. UI grouping uses provider families (`database`, `directory`, `sso`) rather than product names.

- Local Database owns KAORI password credentials and is the only valid Super Admin break-glass source.
- Directory providers own external credentials; KAORI stores identity projection and authorization state only.
- Browser SSO providers own external authentication; KAORI stores the external subject link, lifecycle state, and RBAC role.
- Missing role, inactive role, missing/disabled external provider, invalid identity link, inactive account, or invalid external Super Admin state fail closed and surface as Effective Access findings.

## Break-glass invariant

`is_super_admin` is valid only when `auth_source == 'database'`. At least one active Local Database Super Admin must remain available. External Directory/SSO identities may receive normal RBAC roles but never the break-glass flag.

## Extension rule

Adding a new Identity Provider must not add provider-specific branching to User Management. `app/users` consumes only catalog-derived provider identity/family and identity-link state.

## Legacy AuditEvent Boundary

`AuditEvent` remains part of User Management's dual administrative ledger while shared audit consumers still depend on it. This compatibility ledger must not be removed from User Management in isolation; migration must be coordinated with every consumer.

## Password Reset Session Boundary

Local password changes and administrator resets advance `User.auth_session_version` to revoke all existing authenticated sessions and remembered sign-ins for the affected credential generation. Self-service change may re-establish only the current browser on the new generation.
