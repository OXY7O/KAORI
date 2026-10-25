# Authentication Test Plan

## Automated Function Tests

The canonical suite is `tests/access/authentication/`.

### Provider Core

- Catalog maps concrete types to `database`, `ldap`, and `sso` families.
- Catalog and runtime browser registry contain the same browser-provider types.
- Unsupported provider types fail closed.
- Provider-form projection writes only fields owned by the selected provider type.
- Provider validation normalizes configuration and protocol failures.

### Credential Orchestration

- Local success is authoritative.
- An existing local identity with a wrong password does not fall through to LDAP.
- Unknown local identity or an existing externally provisioned LDAP account may continue to enabled, linked LDAP providers; the presence of its KAORI projection row does not grant local password authority.
- Database unavailability stops external lookup.
- LDAP provider unavailability is preserved after all external attempts.
- Enabled → Disabled external provider transitions atomically advance auth_session_version only for externally owned linked identities; disabling an already disabled provider, ordinary edits and re-enabling do not rotate generations.
- Old browser and remember cookies fail closed on the next request across app instances; enabling again cannot restore previous generations.
- Provider disablement does not revoke unrelated providers' user projections or Local Database break-glass users. If the same KAORI external account links multiple provider instances of the same source, its sessions are conservatively revoked upon disabling any linked provider; no credential authority is transferred.
- A revocation update or provider commit failure rolls back the transaction; the Activity Audit event records a count of linked accounts, not the number of active sessions.

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
- A successful Local, LDAP or SSO login atomically increments its own user's session generation; old signed browser and remember cookies are denied on the next request while unrelated accounts remain authenticated.
- Concurrent login transactions for the same user serialize generation increments. The response must bind to **its own** UPDATE RETURNING generation rather than an ORM refresh that could observe the newer login's generation.
- Failed credentials, account disabled/deleted before issuance, source mismatch or SQL error must not commit a replacement generation or permit a new authenticated session.
- The non-secret login-specific `auth_session_ref` is safe in success/login and logout Activity Audit only. A failed login may name a target user but cannot inherit authenticated actor or active-session correlation from other sessions.
- Multiple browser tabs sharing the same copied signed cookie are out of scope for the one-login-generation guarantee; test that distinction rather than describing the feature as one physical device.
- Guided two-browser UAT verifies Browser A login then Browser B login as the same user, A rejected, B allowed, optional remember-me old cookie rejected, independent user unaffected and clean audit correlation; also exercise two parallel login requests and provider-disable/password-change regressions.
- Super-admin remember-me is denied unless explicitly enabled.
- Logout clears auth and step-up state.
- Readiness requires every table touched by the login path.
- Concrete SSO sources map to the SSO family.
- Unknown sources cannot manage a KAORI password.

### Architecture Contracts

- LDAP protocol code belongs to `app/access/authentication`.
- Combined OAuth module and Users-owned LDAP package remain absent.
- User routes delegate provider projection/validation to Authentication.
- Routes use strategy lookup and shared SSO flow validation rather than provider branches.
- ORM models do not duplicate catalog predicates.

## Route and Integration Tests

Run inside the KAORI dev container:

```bash
pytest -q tests/access/authentication
pytest -q tests/access/authentication --cov=app.access.authentication --cov-report=term-missing
```

Route/integration coverage must verify CSRF, login GET/POST, authenticated redirect, login metadata, normalized flashes, rate-limit responses, SSO start/callback, POST-only logout, and Activity Audit records.

## Manual Provider Matrix

Test Local Database, LDAP, Google OIDC, and GitHub OAuth with:

- valid active identity;
- wrong credential or denied authorization;
- inactive KAORI projection;
- disabled provider;
- provider disabled **while already signed in** (old session rejected on next request; fresh login blocked; re-enable requires new session);
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
