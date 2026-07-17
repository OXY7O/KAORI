# Authentication provider integration contract

## Common normalized outcome

Every provider must return or produce a provider-neutral result containing success, safe reason code, provider source, optional resolved user/identity projection, and a safe user-facing message. Raw exceptions remain internal.

## Local database

Inputs are username and password. The provider queries only non-deleted accounts, verifies the password hash, checks active state, and never reveals whether a username exists through its public message.

## LDAP / Active Directory requirements

Before activation, define:

- server URI and mandatory TLS mode;
- CA trust and hostname validation;
- connect/read timeout and retry boundary;
- service-bind versus direct-bind strategy;
- escaped search filter and base DN;
- immutable subject attribute;
- username, email, display-name, and group attributes;
- nested group handling;
- disabled/expired account interpretation;
- fail-closed behavior;
- group normalization passed to role mapping.

The adapter must not persist or log user passwords or bind secrets.

## OIDC requirements

Before activation, define:

- issuer and discovery metadata validation;
- client ID and secret reference;
- exact redirect URI;
- authorization code flow;
- state, nonce, PKCE, signature, issuer, audience, time, and `at_hash` validation as applicable;
- immutable `sub` as the provider identity key;
- allow-listed claims for local projection and mapping;
- logout/session behavior;
- key rotation and provider outage behavior.

## SAML requirements

Implement only for a confirmed deployment requirement. Require trusted metadata, signed response/assertion policy, audience and recipient validation, clock-skew bounds, replay protection, secure XML parsing, and immutable NameID/attribute identity rules.

## Availability and fallback

External provider outage may block that provider but must not silently fall back using the same submitted credentials against another provider. The user or routing policy must explicitly select the provider. The local break-glass path remains separately available.

## Role mapping handoff

Providers emit normalized groups/claims only. RBAC owns mapping rules, precedence, fallback role, conflicts, synchronization, deprovisioning, and administrator safeguards. This contract will be expanded during the next RBAC/role-mapping review.
