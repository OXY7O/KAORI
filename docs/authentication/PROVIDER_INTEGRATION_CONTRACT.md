# Identity Provider Integration Contract

## Canonical Architecture

Identity Provider is an Access / Authentication capability. It follows the same provider architecture used by KAORI Integrations without becoming part of the infrastructure `app/integrations/` domain.

The canonical hierarchy is:

```text
Access
→ Identity Provider
→ Provider
→ Adapter
→ Admission / Projection Policy
→ KAORI User Projection
→ RBAC
```

Provider definitions are source-controlled in `app/definitions/catalogs/auth/identity_provider/providers.yaml`. Runtime vocabulary is loaded by `app/auth/identity_provider/catalog.py`.

Core code uses these independent identifiers:

- `provider_key`: product or authority identity, such as `google`, `github`, or `ldap_directory`;
- `adapter_key`: technical protocol implementation, such as `google_oidc`, `github_oauth2`, or `ldap`;
- `family`: `database`, `directory`, or `sso`;
- `flow`: `credentials` or `browser`;
- `configuration_profile`: configuration shape owned by the adapter;
- `admission_policy`: projection or JIT admission contract.

Adding a provider that reuses an existing adapter must not require schema, route, user-lifecycle, or RBAC changes.

## Folder Contract

Authentication kernel code lives under:

```text
app/auth/identity_provider/
├── catalog.py
├── configuration.py
├── credential.py
├── directory.py
├── browser.py
├── registry.py
├── adapters/
└── providers/
```

Provider-specific behavior belongs under `providers/<provider>/`. Reusable protocol behavior belongs under `adapters/<adapter>/`.

The administrative workspace is separate:

```text
app/identity_providers/
app/templates/access/identity_providers/
```

User lifecycle remains in `app/users/`. Identity-provider administration must not be reintroduced into User Management.

## Common Normalized Outcome

Credential adapters return `AuthResult` with:

- success state;
- stable reason code;
- canonical provider source;
- optional resolved KAORI user;
- safe user-facing message.

Browser adapters return a normalized SSO identity. `app/auth/sso.py` owns identity-link resolution, controlled JIT admission, and conversion to `AuthResult`. Raw protocol exceptions never cross the HTTP boundary.

Directory adapters return a normalized `ExternalIdentity`. Administrative provisioning consumes this generic contract and never calls an LDAP implementation directly.

## Local Database Contract

Local Database is the KAORI-owned credential authority and the only valid break-glass Super Admin source.

Inputs are username and password. Authentication queries only non-deleted users, verifies a password only when `auth_source=database`, checks lifecycle state, and uses a dummy hash for unknown or external usernames to reduce timing distinction.

An existing Local Database identity is authoritative. Wrong local credentials do not fall through to a directory provider.

## Directory Provider Contract

A directory provider is selected by `provider_key`; application code dispatches the technical implementation through `adapter_key`.

The current `ldap` adapter owns:

- URI parsing for `ldap://` and `ldaps://`, including IPv6-safe host/port handling;
- mandatory certificate validation for LDAPS or StartTLS;
- bounded connect and receive timeout;
- service bind and escaped directory search;
- immutable subject conversion and explicit attribute projection;
- direct user bind using the provisioned DN;
- distinction between invalid credentials and provider/transport failure.

Directory authentication requires an enabled `IdentityProvider` record and a provisioned `ExternalIdentityLink`. Passwords and bind secrets must not be persisted or logged.

The administrative Directory Provisioning flow must use the registered directory adapter and a short-lived signed projection proof. Browser-controlled hidden identity fields are not authoritative evidence.

## Browser SSO Contract

Every browser adapter implements the shared browser-provider protocol and is registered by `adapter_key`.

The shared route owns state generation, hashed state persistence, bounded flow TTL, callback ordering, and session establishment. Provider packages own provider-specific protocol exchange and identity validation.

OIDC implementations validate discovery metadata, issuer, audience, signature, temporal claims, immutable subject, and nonce when required. OAuth implementations resolve an immutable provider subject and only the allow-listed profile fields needed by KAORI.

A future provider that reuses an existing adapter is added to the catalog without adding a route branch. A genuinely different protocol adds a new adapter package and registry entry.

## Identity Projection and JIT

Pre-provisioned access resolves by provider instance plus immutable external subject. Controlled JIT requires:

- an active non-admin default role;
- provider-specific admission policy;
- explicit admission evidence defined by the provider catalog;
- conflict checks against existing active username/email projections.

Providers never assign hidden permissions. RBAC remains authoritative after the local user projection is resolved.

## Availability and Credential Fallback

Browser providers are explicitly selected by the user and never fall back to another browser provider.

The shared username/password form follows an explicit authority policy: Local Database first, then eligible directory credential adapters only when no Local Database identity owns the username. Database unavailability stops the flow because identity-link resolution depends on PostgreSQL. External provider outages are normalized as provider-unavailable outcomes.

The Local Database Super Admin path remains independent for recovery.

## Required Tests for a New Provider

A provider is incomplete until tests cover:

- catalog and registry consistency;
- provider-key and adapter-key projection;
- configuration validation;
- success, invalid identity, inactive account, storage failure, and provider outage;
- immutable subject behavior and projection conflicts;
- state/nonce/TTL controls for browser flows where applicable;
- signed projection evidence for administrative directory provisioning;
- secret and payload non-persistence;
- route thinness and absence of provider-specific branches in core workspace code;
- manual validation against the actual provider in a non-production environment.
