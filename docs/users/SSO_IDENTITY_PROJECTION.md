# SSO Identity Projection

Google and GitHub identities are represented by the existing centralized models in `app/models/identity.py`.

```text
IdentityProvider
ExternalIdentityLink
User
Role
```

No ORM model is located inside `app/auth/` or `app/users/`.

## Projection identity

```text
Google: provider_id + Google sub
GitHub: provider_id + numeric GitHub user ID
```

The projection synchronizes safe profile attributes such as display name, email, and external username. It does not synchronize passwords or authorization tokens.

## JIT projection

When JIT is enabled and admission succeeds, KAORI creates:

1. a `users` row with no local password;
2. an `external_identity_links` row;
3. the configured non-admin role assignment;
4. an active lifecycle state.

Conflicting usernames are deterministically de-duplicated. Conflicting email ownership is rejected rather than silently linked.

## Existing projection

When a projection already exists, the provider authenticates the identity and KAORI remains authoritative for:

- active, inactive, or deleted lifecycle state;
- role and permission assignment;
- administrative restrictions;
- audit and login activity.
