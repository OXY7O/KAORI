# Authentication Provider Integration Contract

## Canonical Registration

Every provider is declared in `app/auth/providers/catalog.py` with a concrete type, family, display label, flow, configuration posture, and JIT capability. Protocol behavior is registered once in `app/auth/providers/registry.py`.

A new implementation must not add provider-specific branching to `app/auth/routes.py` or `app/users/routes.py`.

## Common Normalized Outcome

Credential providers return `AuthResult` with:

- success state;
- stable reason code;
- concrete provider source;
- optional resolved KAORI user;
- safe user-facing message.

Browser providers return `SsoIdentity`; `app/auth/sso.py` owns link resolution, JIT admission, and conversion to `AuthResult`. Raw protocol exceptions never cross the HTTP boundary.

## Local Database Contract

Inputs are username and password. The provider queries only non-deleted users, verifies a Local Database password only when `auth_source=database`, checks lifecycle state, and uses a dummy hash for unknown/external usernames to reduce timing distinction.

An existing Local Database identity is authoritative. Wrong local credentials do not fall through to LDAP.

## LDAP / Active Directory Contract

The LDAP implementation owns:

- URI parsing for `ldap://` and `ldaps://` including IPv6-safe host/port handling;
- mandatory certificate validation for LDAPS or StartTLS;
- bounded connect and receive timeout;
- service bind and escaped directory search;
- immutable subject conversion and explicit attribute projection;
- direct user bind using the provisioned DN;
- distinction between `invalidCredentials` and provider/transport failure.

LDAP authentication requires an enabled `identity_providers` record and a provisioned `external_identity_links` row. Passwords and bind secrets must not be persisted or logged.

## Browser SSO Contract

Every browser adapter implements `BrowserSsoProvider`:

- `build_authorization_url()`;
- `exchange_code()`;
- `validate_configuration()`;
- explicit `provider_type` and `requires_nonce` declarations.

The shared route owns state generation, hashed state persistence, bounded flow TTL, callback ordering, and session establishment. Provider adapters own protocol-specific token exchange and identity validation.

OIDC adapters validate discovery metadata, issuer, audience, signature, temporal claims, immutable subject, and nonce. OAuth adapters resolve an immutable provider subject and only the allow-listed profile fields needed by KAORI. PKCE must be added at the shared browser-flow boundary when required by a future provider or deployment policy; it must not be implemented as a route-local branch.

## Identity Projection and JIT

Pre-provisioned access resolves by provider ID plus immutable subject. Controlled JIT requires:

- an active non-admin default role;
- provider-specific admission allow-list;
- verified Google email for domain admission;
- GitHub subject or username admission;
- conflict checks against existing active username/email projections.

Providers never assign hidden permissions. RBAC remains authoritative after the local user projection is resolved.

## Availability and Credential Fallback

Browser providers are explicitly selected by the user and never fall back to another browser provider.

The shared username/password form uses a documented authority policy: Local Database first, then enabled LDAP links only when no Local Database identity owns the username. Database unavailability stops the flow because external identity-link resolution also depends on PostgreSQL. LDAP operational failure is reported as provider unavailable after all matching LDAP links are evaluated.

The separately controlled Local Database super-admin path remains available for recovery.

## Required Tests for a New Provider

A provider is incomplete until tests cover:

- catalog and registry consistency;
- configuration projection and validation;
- success, invalid identity, inactive account, storage failure, and provider outage;
- immutable subject behavior and projection conflicts;
- state/nonce/TTL controls for browser flows;
- secret and payload non-persistence;
- route-thinness and absence of provider-specific branches;
- manual validation against the actual provider in a non-production environment.
