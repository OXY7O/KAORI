# KAORI Authentication Domain

## Purpose

`app/auth` is the identity-verification boundary for KAORI. It verifies credentials or browser SSO assertions, normalizes outcomes, applies account-state checks, establishes or clears the Flask session, records authentication activity, and hands the authenticated user to the role-aware Welcome workspace.

Authentication answers **who the user is**. Authorization remains owned by `app/rbac`; account administration remains owned by `app/users`.

## Provider Model

KAORI exposes three primary provider families:

| Family | Concrete types | Flow | Credential authority |
| --- | --- | --- | --- |
| Database | `database` | Username/password | KAORI |
| LDAP | `ldap` | Username/password with directory bind | LDAP / Active Directory |
| SSO | `google_oidc`, `github_oauth` | Browser redirect/callback | Google or GitHub |

The distinction between **family** and **concrete provider type** is intentional. User filters and credential ownership operate on the family, while protocol adapters and identity links use the concrete type.

The canonical catalog is `app/auth/providers/catalog.py`. New provider types must be registered there and, for browser SSO, in `app/auth/providers/registry.py`.

## Dependency Direction

```text
app/users forms -> app/users/provider_forms.py -> Auth configuration DTO
                                              |
                                              v
                                  app/auth provider services
                                              |
                                              v
                                  app/models persistence records
```

`app/auth` does not import `app/users`. LDAP connection, TLS, search, and bind behavior are owned by `app/auth/providers/ldap.py`; User Management maps WTForms into `IdentityProviderConfiguration` and invokes the Auth boundary for provider validation, directory search, and administrative projection.

## File Responsibilities

### Domain Files

| File | Responsibility |
| --- | --- |
| `results.py` | Provider-neutral `AuthResult`, reason codes, and safe messages. |
| `admission.py` | Final account/source/role admission gate shared by new logins and existing sessions. |
| `services.py` | Credential-flow orchestration and local-authority fallback rules. |
| `routes.py` | HTTP boundary for login, SSO start/callback, logout, rate limits, and response handling. |
| `session.py` | Session rotation, Flask-Login establishment, remember-me policy, and auth-owned cleanup. |
| `sso.py` | SSO provider lookup, external identity resolution, JIT admission, projection, and link synchronization. |
| `provider_configuration.py` | Provider-neutral configuration DTO, canonical key validation, model projection, and provider validation dispatch. |
| `readiness.py` | Database/schema readiness for every table needed by authentication. |
| `audit.py` | Authentication Activity Audit writer with safe provider, IP, browser, OS, and device metadata. |
| `user_agent.py` | Stateless user-agent parsing. |

### Provider Files

| File | Responsibility |
| --- | --- |
| `providers/catalog.py` | Canonical provider types, families, flows, labels, and configurable choices. |
| `providers/base.py` | `CredentialAuthProvider` protocol for username/password providers. |
| `providers/registry.py` | Credential registry plus explicit browser-SSO strategy registry. |
| `providers/database.py` | Local database password verification and database-error normalization. |
| `providers/ldap.py` | LDAP directory client, TLS/search/bind behavior, and LDAP credential adapter. |
| `providers/browser.py` | Browser SSO contract, normalized identity, state/nonce helpers, secret lookup, and timeout policy. |
| `providers/google_oidc.py` | Google authorization, token exchange, ID-token verification, nonce enforcement, and discovery validation. |
| `providers/github_oauth.py` | GitHub authorization, token exchange, profile/email lookup, and endpoint validation. |

## Credential Authentication Flow

1. `POST /auth/login` passes CSRF and login rate-limit checks.
2. `services.authenticate()` builds the credential registry.
3. The Local Database provider runs first and remains authoritative when a local user exists.
4. Only an unknown local identity may fall through to LDAP.
5. LDAP resolves all matching enabled identity links and performs directory binds through `LdapDirectoryClient`.
6. Invalid credentials, inactive users, provider outages, source mismatches, and inactive/missing roles return normalized `AuthResult` values.
7. `admission.enforce_login_admission()` is the single final gate before session establishment; non-super-admin users require an active role and the verified provider must match the account owner.
8. Credential failures expose one generic public rejection message except a platform-wide database outage; detailed reason codes remain audit-only.
9. Login metadata is committed before session establishment.
10. A successful Activity Audit event is written only after the session has been established.

This prevents a local username collision from silently authenticating against LDAP and prevents a failed metadata commit from being recorded as a completed login.

## Browser SSO Flow

1. `/auth/sso/<provider>/start` resolves an enabled provider from the identity-provider registry.
2. The browser strategy is selected by concrete provider type.
3. KAORI stores only the state fingerprint, provider ID, nonce when required, and start timestamp in the session.
4. The callback validates provider identity, state, and the configured `AUTH_SSO_FLOW_TTL_SECONDS` window.
5. The registered strategy exchanges and validates the authorization code.
6. `sso.resolve_sso_identity()` resolves a pre-provisioned link or applies controlled JIT admission.
7. Account state, provider ownership, and role admission are normalized before session establishment.
8. A validated internal `next` target is carried through the signed SSO flow and revalidated before redirect; external and protocol-relative targets are rejected.

## Security Invariants

- Local Database authentication remains available as the controlled recovery provider.
- Authentication and authorization remain separate domains.
- Passwords, hashes, bind secrets, authorization codes, tokens, assertions, and raw provider payloads are never written to Activity Audit Log.
- Unknown provider types are rejected by the provider catalog; unknown identity sources never gain KAORI password ownership.
- LDAP invalid credentials are distinguished internally from LDAP operational outages without exposing raw directory errors.
- LDAP transport mode and URI scheme must agree; plaintext LDAP remains disabled unless `AUTH_LDAP_ALLOW_PLAINTEXT=true` is explicitly enabled for a controlled development environment.
- Google OIDC requires a nonce at authorization and callback validation.
- SSO state is stored as a SHA-256 fingerprint rather than raw state.
- Successful login clears prior session state before authentication state is retained.
- Login and SSO post-authentication redirects accept only same-origin absolute-path targets; schemes, authorities, protocol-relative URLs, backslashes, and control characters are rejected.
- Non-super-admin sessions require an active role, and provider ownership is revalidated both at login and by the Flask-Login user loader on later requests.
- The `super_admin` break-glass authority is valid only through the Local Database provider.
- Logout is POST-only and CSRF-protected. The Flask-Login remember-cookie revocation marker is preserved during session cleanup so logout cannot silently recreate the session.
- Persistent login remains disabled for super administrators unless `AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME=true` is explicitly configured.
- Normal remember-me persistence defaults to 7 days and is bounded to 1-30 days by `AUTH_REMEMBER_ME_DAYS`.
- Local Database sessions are bound to `User.auth_session_version` through the Flask-Login user identifier. Password changes/resets advance the generation so older sessions and remember cookies fail closed on their next request.
- Self-service password change refreshes only the current browser onto the new generation and clears its remember cookie; administrator or CLI password reset preserves no target session.
- Legacy pre-generation session identifiers are accepted only while the user remains on generation `1`; after any password change, a missing generation is rejected.
- Authentication rate-limit rejections are persisted as audit-only `rate_limited` events.
- Authentication Audit schema `authentication.v2` separates a resolved target account from an authenticated actor; failed attempts never claim the target user's email, display name, or role as actor identity.
- Authentication request evidence stores `request.path`, never callback query strings, so OAuth authorization codes are excluded from the audit record.
- Production proxy trust remains centralized in `ProxyFix`; authentication reads `request.remote_addr` only.

## Readiness Contract

Authentication is not ready until these tables exist:

- `users`
- `roles`
- `permissions`
- `identity_providers`
- `external_identity_links`
- `notifications`

The last two are required because LDAP/SSO identity resolution and authentication Activity Audit persistence are part of the login path.

## Test Gate

Functional Auth tests live under `tests/auth/`; architecture ownership checks live under `tests/contracts/auth/`.

```bash
pytest -q tests/auth -m functional
pytest -q tests/contracts/auth -m contract
pytest -q tests/auth -m functional --cov=app.auth --cov-report=term-missing
```

The security regression contracts specifically cover session admission, safe post-login redirects, remember-cookie revocation, bounded remember-me duration, rate-limit audit evidence, and `authentication.v2` actor/target semantics.

The functional gate covers provider family/type mapping, credential orchestration, Database behavior, LDAP transport and bind semantics, browser SSO strategy selection and token projection, SSO identity resolution, provider configuration projection, session policy, readiness, and login transaction boundaries. Contract tests are guardrails and are not counted as evidence that a function works.

## Extension Rule

Adding another provider must not add provider-specific branching to `app/auth/routes.py` or `app/users/routes.py`.

For another browser SSO provider:

1. add the concrete type to `providers/catalog.py`;
2. implement `BrowserSsoProvider` in a dedicated module;
3. register the adapter in `providers/registry.py`;
4. add provider-specific configuration fields and validation only where required;
5. add unit tests for authorization URL, callback validation, admission, and configuration validation.

For another credential provider, implement `CredentialAuthProvider` and register it in the credential registry with an explicit authority and collision policy.
