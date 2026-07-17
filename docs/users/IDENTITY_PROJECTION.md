# Identity Projection

## Principle

KAORI must not import an entire enterprise directory by default. External users enter KAORI through one of two controlled paths:

1. administrator provisioning: search the configured provider, select one identity, create a projection, assign initial role;
2. just-in-time provisioning: successful external authentication creates or updates a projection under an explicit JIT policy.

## Required immutable key

- LDAP: provider ID plus stable directory object identifier or DN strategy.
- OIDC: issuer plus `sub`.
- SAML: provider/entity ID plus stable NameID or configured immutable attribute.

Email and username are display/search attributes, not immutable identity keys.

## Password ownership

External credentials are never entered, stored, reset, or verified by KAORI. User Management must show `Managed by external identity provider` and omit password fields from the submitted payload.
