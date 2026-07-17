# Authentication data model

## Current model

### `users`

Current authentication-relevant fields include username, email, display name, password hash, legacy and normalized role references, authentication source, external ID, active/deleted state, super-admin marker, last-login metadata, and timestamps.

### `auth_login_events`

Current fields include attempted username, optional user ID, provider source, success flag, normalized reason, IP address, user agent, and creation time.

## Target model decisions before migrations

The following additions require a dedicated migration and compatibility review rather than ad-hoc columns during the UI review:

### Account security fields

- `is_break_glass` — explicit recovery-account marker independent from ordinary super-admin status.
- `failed_login_count` — durable identity-level failure counter.
- `last_failed_login_at` — support decay and incident analysis.
- `locked_until` — time-bound lockout.
- `password_changed_at` — rotation and age policy.
- `must_change_password` — controlled bootstrap/reset flow.

### External identity projection

Prefer a separate `external_identities` table when multiple providers or identities per user are possible:

```text
external_identities
- id
- user_id
- provider_id
- subject_identifier
- normalized_username
- email_snapshot
- attributes_snapshot (strictly allow-listed)
- last_authenticated_at
- created_at
- updated_at
- disabled_at
```

The stable uniqueness key is provider plus immutable subject/DN identifier, not mutable email or display name.

### Provider configuration

Provider secrets must not be stored as plaintext model fields. A provider registry may store non-secret metadata and secret references. Validation state and last validation timestamp belong to the integration configuration domain.

### Role mapping

Role mapping is intentionally deferred to the RBAC design stage. It should consume normalized provider groups/claims and produce an explicit KAORI role assignment with precedence, fallback, conflict, and removal behavior documented before schema creation.

## Data minimization

Do not persist raw OIDC claims, LDAP entries, SAML assertions, access tokens, refresh tokens, ID tokens, passwords, cookies, or complete provider responses. Any attribute snapshot must be allow-listed and justified for operations or audit.
