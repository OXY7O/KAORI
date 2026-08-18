# KAORI Authentication Domain

## Identity Provider architecture

External authentication follows `identity_provider -> provider_key -> adapter_key -> capability/admission policy`. Provider identity and technical adapter identity are separate. The source-controlled catalog is `app/definitions/catalogs/access/authentication/identity_provider/providers.yaml`; the kernel is `app/access/authentication/identity_provider/`; administrative UI is `app/access/identity_providers/`.

- Directory providers reuse registered directory/credential adapters such as `ldap`.
- Browser providers register provider-specific implementations behind an `adapter_key`.
- Core login/session routes do not branch on Google, GitHub, LDAP, or future product names.
- Provider records persist canonical identity plus JSON adapter configuration and admission policy; secret values remain external environment references.


## Purpose

`app/access/authentication` is the identity-verification boundary for KAORI. It verifies credentials or browser SSO assertions, normalizes outcomes, applies account-state checks, establishes or clears the Flask session, records authentication activity, and hands the authenticated user to the role-aware Welcome workspace.

Authentication answers **who the user is**. Authorization remains owned by `app/access/rbac`; account administration remains owned by `app/access/users`.

## Provider Model

KAORI groups authentication by family while keeping product identity and technical adapter identity separate.

| Family | Example provider keys | Example adapter keys | Flow |
| --- | --- | --- | --- |
| Database | `database` | `local_database` | Username/password |
| Directory | `ldap_directory` | `ldap` | Username/password with directory bind |
| SSO | `google`, `github` | `google_oidc`, `github_oauth2` | Browser redirect/callback |

The provider catalog is source-controlled in `app/definitions/catalogs/access/authentication/identity_provider/providers.yaml`. Adding a provider that reuses an existing adapter changes the catalog/provider package only; core schema, User Management, and auth routes remain unchanged.

## Dependency Direction

```text
app/access/users forms -> app/access/identity_providers/forms.py -> Auth configuration DTO
                                              |
                                              v
                                  app/access/authentication provider services
                                              |
                                              v
                                  app/models persistence records
```

`app/access/authentication` does not import `app/access/users`. LDAP connection, TLS, search, and bind behavior are owned by `app/access/authentication/identity_provider/adapters/ldap/client.py`; Identity Provider administration maps WTForms into `IdentityProviderConfiguration` and invokes the Auth boundary for provider validation, directory search, and administrative projection.

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
| `identity_provider/configuration.py` | Provider-neutral configuration DTO, canonical key validation, model projection, and provider validation dispatch. |
| `readiness.py` | Database/schema readiness for every table needed by authentication. |
| `audit.py` | Authentication Activity Audit writer with safe provider, IP, browser, OS, and device metadata. |
| `user_agent.py` | Stateless user-agent parsing. |

### Provider Files

| File | Responsibility |
| --- | --- |
| `identity_provider/catalog.py` | Canonical provider definitions, families, flows, labels, and configurable choices. |
| `identity_provider/credential.py` | Provider-neutral credential-adapter protocol. |
| `identity_provider/registry.py` | Credential registry plus explicit browser-SSO strategy registry. |
| `local_database.py` | Local database password verification and database-error normalization. |
| `identity_provider/adapters/ldap/client.py` | LDAP directory client, TLS/search/bind behavior, and LDAP credential adapter. |
| `identity_provider/browser.py` | Browser SSO contract, normalized identity, state/nonce helpers, secret lookup, and timeout policy. |
| `identity_provider/providers/google/browser.py` | Google authorization, token exchange, ID-token verification, nonce enforcement, and discovery validation. |
| `identity_provider/providers/github/browser.py` | GitHub authorization, token exchange, profile/email lookup, and endpoint validation. |

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
2. The browser strategy is selected by provider identity and adapter key.
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
- Unknown provider identities are rejected by the provider catalog; unknown identity sources never gain KAORI password ownership.
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

Functional Auth tests live under `tests/access/authentication/`; architecture ownership checks live under `tests/contracts/access/authentication/`.

```bash
pytest -q tests/access/authentication -m functional
pytest -q tests/contracts/access/authentication -m contract
pytest -q tests/access/authentication -m functional --cov=app.access.authentication --cov-report=term-missing
```

The security regression contracts specifically cover session admission, safe post-login redirects, remember-cookie revocation, bounded remember-me duration, rate-limit audit evidence, and `authentication.v2` actor/target semantics.

The functional gate covers provider family/provider/adapter mapping, credential orchestration, Database behavior, LDAP transport and bind semantics, browser SSO strategy selection and token projection, SSO identity resolution, provider configuration projection, session policy, readiness, and login transaction boundaries. Contract tests are guardrails and are not counted as evidence that a function works.

## Extension Rule

Adding another provider must not add provider-specific branching to `app/access/authentication/routes.py` or `app/access/identity_providers/routes.py`.

For another browser SSO provider:

1. add the provider definition to the source-controlled catalog;
2. implement the provider browser adapter in `identity_provider/providers/<provider>/`;
3. register the adapter in `identity_provider/registry.py`;
4. add provider-specific configuration fields and validation only where required;
5. add unit tests for authorization URL, callback validation, admission, and configuration validation.

For another credential provider, implement `CredentialAuthAdapter` and register it in the credential registry with an explicit authority and collision policy.


## Authentication Surface Final Lock v1

Authentication Surface v1 is final-locked for the unauthenticated **Login** and **Database Setup Required** presentation surfaces. The lock preserves the compact 14-inch presentation contract, KAORI Violet identity, light/dark mode, accessible password visibility and theme controls, generic failure copy, and provider-neutral pre-authentication messaging.

Security ownership remains unchanged: `app/access/authentication/routes.py` owns login/SSO/logout HTTP boundaries, `app/access/authentication/session.py` owns safe redirect and session persistence policy, provider adapters own protocol validation, and Activity Audit owns authentication evidence. The final lock specifically preserves safe redirect handling, POST-only CSRF-protected logout, bounded remember-me persistence, default-deny super-admin remember-me, SSO state/nonce/TTL validation, and actor-versus-target audit semantics.

The interactive password/theme runtime is owned by `app/static/js/auth_login.js`. Only the early pre-paint theme bootstrap remains inline in `layouts/auth.html`; this is intentional to prevent a light-theme flash before CSS is applied. Authentication templates may not reintroduce arbitrary text sizes, arbitrary tracking, `font-extrabold`, uppercase presentation utilities, or inline DOM handlers.

Permanent release evidence:

- Static Quality: `scripts/verify_authentication_surface_final_lock.py`, Ruff, djLint, Pyright, UI debt verifiers, and JavaScript syntax.
- Contract Tests: `tests/contracts/access/authentication/`.
- Unit Tests: `tests/unit/access/authentication/test_auth_session_policy.py`.
- Functional Tests: `tests/access/authentication/test_login_characterization.py`.
- Security Regression: `tests/security/access/authentication/test_authentication_security.py`.
- Rendering/UI Contracts: `tests/rendering/access/authentication/test_authentication_rendering.py`.
- End-to-End Smoke: `tests/e2e/access/authentication/test_authentication_smoke.py`.
- Integration: N/A for this presentation lock. Provider/storage integrations are unchanged; this batch does not introduce a new persistence, LDAP, OAuth/OIDC, or external-runtime collaboration boundary.
