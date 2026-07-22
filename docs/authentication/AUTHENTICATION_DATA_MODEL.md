# Authentication Data Model

## Current Persistence Authority

### `users`

Authentication-relevant fields are:

- `username`, `email`, and `display_name` for the KAORI user projection;
- `password_hash` for Local Database credentials only;
- `role_id` as the single RBAC role reference;
- `auth_source` as the concrete primary source: `database`, `ldap`, `google_oidc`, or `github_oauth`;
- `external_id` as a compatibility projection of the primary external subject;
- lifecycle state through `is_active` and `deleted_at`;
- emergency privilege through `is_super_admin`;
- `last_login_at`, `last_login_ip`, and `last_auth_source` for login metadata.

`users.auth_source` uses concrete provider types, not provider-family labels such as `sso`.

### `identity_providers`

One record stores the non-secret configuration for an LDAP, Google OIDC, or GitHub OAuth provider instance. The model includes:

- stable key, display name, concrete provider type, enabled state, and JIT state;
- LDAP endpoint, bind-secret reference, search/filter, TLS, timeout, and attribute mapping;
- browser SSO issuer/client metadata and client-secret reference;
- JIT default role and provider-specific admission allow-lists.

Runtime secrets are referenced by environment-variable name and are never stored in the table.

### `external_identity_links`

This table is the stable mapping between one KAORI user and one provider identity. Its uniqueness contracts are:

- provider plus immutable subject is globally unique;
- one user has at most one identity link for a specific provider instance.

The link stores only the required projection: subject, external username, optional DN, email/display-name snapshots, projection type, and synchronization timestamps. Mutable email or display name is never the identity key.

### Authentication Activity Audit

Login and logout events are written to the unified `notifications` table using:

- `event_type = authentication`;
- schema marker `authentication.v1` in `metadata_json`;
- normalized action, source, result, reason code, client context, and known actor projection.

These rows are audit-only and are marked read so they do not create personal notification noise. The retired `auth_login_events` table is not a runtime dependency.

## Identity Authority Rules

- Local Database credentials are valid only for a user whose `auth_source` is `database`.
- LDAP authentication resolves through an enabled LDAP provider and an `external_identity_links` row.
- Browser SSO resolves through provider ID plus immutable external subject.
- Unknown source values fail closed and do not receive KAORI password ownership.
- A local username collision is authoritative: an existing Local Database user with a wrong password does not fall through to LDAP.

## Data Minimization

Do not persist raw OIDC claims, LDAP entries, access tokens, refresh tokens, ID tokens, authorization codes, passwords, cookies, or complete provider responses. Any future snapshot must be allow-listed and justified for operations or audit.

## Deferred Account-Security Fields

Durable identity lockout is not yet modeled. A future migration may add `failed_login_count`, `last_failed_login_at`, `locked_until`, `password_changed_at`, `must_change_password`, and an explicit `is_break_glass` marker. These fields must be implemented with service-level tests and Activity Audit behavior, not appended only for UI display.
