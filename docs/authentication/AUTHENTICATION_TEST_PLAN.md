# Authentication Test Plan

## Automated Function Tests

The canonical suite is `tests/auth/`.

### Provider Core

- Catalog maps concrete types to `database`, `ldap`, and `sso` families.
- Catalog and runtime browser registry contain the same browser-provider types.
- Unsupported provider types fail closed.
- Provider-form projection writes only fields owned by the selected provider type.
- Provider validation normalizes configuration and protocol failures.

### Credential Orchestration

- Local success is authoritative.
- An existing local identity with a wrong password does not fall through to LDAP.
- Unknown local identity may continue to enabled LDAP providers.
- Database unavailability stops external lookup.
- LDAP provider unavailability is preserved after all external attempts.

### Local Database Provider

- Valid active user succeeds.
- Unknown username and wrong password have the same public rejection.
- External-source user does not receive Local Database password ownership.
- Inactive user is rejected.
- SQLAlchemy failure becomes `database_unavailable` and rolls back.

### LDAP

- URI, port, LDAPS, StartTLS, TLS certificate validation, timeout, and bind-secret handling are covered.
- Search input is escaped and filter placeholders are constrained.
- Stable binary subjects are normalized deterministically.
- User bind distinguishes invalid credentials from provider outage.
- Enabled links are matched case-insensitively and tried deterministically.
- Inactive, storage failure, invalid credentials, and provider-unavailable outcomes are normalized.

### Browser SSO

- Strategy registry is explicit and consistent with the catalog.
- Authorization URLs contain required state, scope, callback, and nonce behavior.
- Raw state is not persisted.
- Provider ID, state hash, start timestamp, future timestamp, malformed values, and TTL are validated fail-closed.
- Provider lookup storage failure is normalized.
- Existing identity links, inactive users, controlled JIT, conflicts, and commit failures are covered.

### Session, Readiness, and Identity Ownership

- Successful login clears prior session state and establishes a fresh session.
- Super-admin remember-me is denied unless explicitly enabled.
- Logout clears auth and step-up state.
- Readiness requires every table touched by the login path.
- Concrete SSO sources map to the SSO family.
- Unknown sources cannot manage a KAORI password.

### Architecture Contracts

- LDAP protocol code belongs to `app/auth`.
- Combined OAuth module and Users-owned LDAP package remain absent.
- User routes delegate provider projection/validation to Authentication.
- Routes use strategy lookup and shared SSO flow validation rather than provider branches.
- ORM models do not duplicate catalog predicates.

## Route and Integration Tests

Run inside the KAORI dev container:

```bash
pytest -q tests/auth
pytest -q tests/auth --cov=app.auth --cov-report=term-missing
```

Route/integration coverage must verify CSRF, login GET/POST, authenticated redirect, login metadata, normalized flashes, rate-limit responses, SSO start/callback, POST-only logout, and Activity Audit records.

## Manual Provider Matrix

Test Local Database, LDAP, Google OIDC, and GitHub OAuth with:

- valid active identity;
- wrong credential or denied authorization;
- inactive KAORI projection;
- disabled provider;
- missing secret;
- PostgreSQL unavailable;
- external endpoint unavailable or TLS failure;
- pre-provisioned identity;
- JIT allowed and JIT denied;
- duplicate username/email/subject conflict;
- expired or mismatched SSO callback state.

## Operational Validation

- Redis-backed limiter is shared across production web instances.
- Trusted proxy hop counts match the deployed ingress path.
- Authentication Activity retention/archive lifecycle preserves required evidence.
- Local super-admin recovery is rehearsed under change control.
