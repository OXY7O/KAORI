# Authentication Data Model

## Persistence Authority

### `users`

Authentication-relevant fields include:

- `username`, `email`, and `display_name` for the KAORI user projection;
- `password_hash` for Local Database credentials only;
- `role_id` as the persistent RBAC role reference;
- `auth_source` as the canonical provider key that owns the primary identity, for example `database`, `ldap_directory`, `google`, or `github`;
- `external_id` as a compatibility projection of the primary external subject where still required by existing user data;
- lifecycle state through `is_active` and `deleted_at`;
- break-glass privilege through `is_super_admin`, valid only when `auth_source=database`;
- `last_login_at`, `last_login_ip`, and `last_auth_source` for login metadata.

`users.auth_source` stores provider identity, not protocol names. Adapter identifiers such as `google_oidc` and `ldap` belong to `identity_providers.adapter_key`.

### `identity_providers`

Each row is one configured identity-provider instance. The generic model stores:

- stable instance `key` and `display_name`;
- `provider_key` — product/authority identity;
- `adapter_key` — technical adapter identity;
- enabled and JIT state;
- optional default role for controlled JIT;
- `configuration_json` — non-secret adapter configuration and secret-reference names;
- `admission_policy_json` — provider admission/projection policy;
- lifecycle timestamps.

Provider-specific columns are deliberately prohibited from the shared table. A provider that reuses an existing adapter must not require a schema migration.

Runtime secrets are referenced by environment-variable name and are never stored as plaintext provider credentials.

### `external_identity_links`

This table is the stable mapping between one KAORI user and one configured provider instance.

Uniqueness contracts are:

- provider instance plus immutable subject is globally unique;
- one KAORI user has at most one identity link for a specific provider instance.

The link stores only the required projection: immutable subject, external username, optional distinguished name, email/display-name snapshots, projection type, and synchronization timestamps. Mutable email or display name is never the identity key.

### Authentication Activity Audit

Login and logout events are written to the unified `notifications` table using normalized authentication metadata. Raw provider tokens, authorization codes, complete LDAP entries, or provider payloads are not stored in Activity Audit.

## Identity Authority Rules

- Local Database credentials are valid only for a user whose `auth_source` is `database`.
- Local Database is the only valid Super Admin break-glass authority.
- Directory credential authentication resolves through an enabled provider plus an `ExternalIdentityLink` and then dispatches through that provider's `adapter_key`.
- Browser SSO resolves through provider instance plus immutable external subject.
- Unknown provider or adapter values fail closed.
- Existing Local Database username ownership is authoritative; a wrong local password does not fall through to an external credential adapter.
- Administrative directory provisioning accepts only server-verified signed projection evidence.

## Provider / Adapter Examples

```text
provider_key=google          adapter_key=google_oidc
provider_key=github          adapter_key=github_oauth2
provider_key=ldap_directory  adapter_key=ldap
provider_key=database        adapter_key=local_database
```

Future products may reuse an existing adapter. For example, multiple LDAP-compatible directories can share the `ldap` adapter while maintaining distinct provider keys and provider metadata.

## Data Minimization

Do not persist raw OIDC claims, LDAP entries, access tokens, refresh tokens, ID tokens, authorization codes, passwords, cookies, or complete provider responses. Any future snapshot must be allow-listed and justified for operations or audit.

## Schema Evolution Rule

New provider products must not add product-specific columns to `identity_providers`. A schema migration is justified only when the generic identity-provider contract itself gains a durable cross-provider capability.
