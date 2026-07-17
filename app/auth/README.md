# KAORI Authentication domain

## Purpose

`app/auth` is the identity-verification boundary for KAORI. It verifies a user through an authentication provider, normalizes the result, establishes or clears the web session, records Login Activity, and sends an authenticated user to the role-aware Welcome workspace.

Authentication answers **who the user is**. It does not decide what the user may do. Route access, menu visibility, workspace availability, and operational actions remain enforced by `app/rbac`, permission decorators, and role/permission resolution.

## Provider roadmap

| Provider | Status | Purpose |
|---|---|---|
| Local database | Active | Normal local accounts and the independent break-glass super-admin recovery path. |
| LDAP / Active Directory | Planned | Enterprise directory authentication and later group-to-role mapping. |
| SSO (OIDC first; SAML only when required) | Planned | Federated identity authentication and later claim/group-to-role mapping. |

Local authentication must remain available even after external providers are enabled. LDAP and SSO failures must never remove the controlled recovery path.

## File responsibilities

### Domain files

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker. Keep free of side effects and provider initialization. |
| `forms.py` | WTForms request validation for login and local password changes. Password policy validation belongs in reusable validators when expanded. |
| `results.py` | Provider-neutral typed authentication outcomes, reason codes, and safe user-facing messages. No raw provider exception belongs here. |
| `services.py` | Authentication orchestration. It invokes the active provider chain and returns a normalized `AuthResult`; it must not read Flask request fields or create sessions. |
| `routes.py` | HTTP boundary: form submission, rate limit binding, success/failure response, login metadata update, safe redirect, and logout endpoint. Route functions should remain thin. |
| `session.py` | Session rotation, Flask-Login establishment, persistent-session policy, authentication-source state, and auth-owned session cleanup. |
| `audit.py` | Unified authentication audit boundary. It dual-writes legacy Login Activity and Activity Audit Log records, captures safe provider/IP/client metadata, records logout, and retains legacy cleanup helpers. It must never store credentials, tokens, assertions, or raw exceptions. |

### Provider files

| File | Responsibility |
|---|---|
| `providers/base.py` | `AuthProvider` protocol implemented by every provider adapter. |
| `providers/registry.py` | Resolve configured provider names and expose active provider instances. Local database remains mandatory. |
| `providers/database.py` | Verify local username/password credentials against the KAORI user database and return normalized results. |
| `providers/ldap.py` | Reserved LDAP/Active Directory adapter boundary. It stays inactive until connection, TLS, bind, timeout, identity, and group-mapping contracts are complete. |
| `providers/sso.py` | Reserved federated provider boundary. OIDC should be implemented before SAML unless a deployment requirement says otherwise. |
| `providers/__init__.py` | Stable provider-domain exports only. |

### Login templates

| File | Responsibility |
|---|---|
| `templates/auth/index.html` | Composition shell only. It owns page-level layout and includes the two main panels. |
| `partials/_brand_panel.html` | KAORI positioning and capability cues. Do not place provider controls or authentication logic here. |
| `partials/_feature_cards.html` | Compact platform-value cards shown in the brand panel. |
| `partials/_login_form.html` | Form composition, labels, fields, submit action, theme control, and audit notice. |
| `partials/_login_alerts.html` | Safe success/error messages rendered from Flask flash messages. |
| `partials/_provider_status.html` | Current actionable provider indicator. LDAP/SSO controls must not appear before their routes work. |
| `partials/_footer_meta.html` | Version/legal/environment footer metadata. |

## Current local authentication flow

1. `POST /auth/login` passes CSRF validation and the configured limiter.
2. `routes.login()` calls `services.authenticate()` with username and password.
3. `services.authenticate()` resolves the provider registry and invokes the local database provider.
4. The provider queries a non-deleted user, verifies the password hash, and checks account state.
5. A normalized `AuthResult` is returned; raw SQL/provider errors are not exposed.
6. The attempt is written to Login Activity without credentials.
7. On success, KAORI records last-login metadata, rotates the session, and authenticates through Flask-Login.
8. The user is redirected to `welcome.index`; RBAC controls the workspace and all protected actions.

## Security invariants

- Local database authentication is always available as the recovery provider.
- Authentication and authorization remain separate domains.
- Login errors are generic enough to avoid username enumeration.
- Passwords, hashes, LDAP bind credentials, authorization codes, access/refresh tokens, ID tokens, assertions, and raw provider payloads are never logged.
- Client IP comes from `request.remote_addr`; production proxy trust is centralized in configured `ProxyFix`, not direct parsing of spoofable forwarding headers.
- Successful login rotates the session before authentication state is established.
- Logout is POST-only and CSRF-protected.
- Persistent login for super administrators is disabled by default through `AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME=false`.
- Production cookies are Secure, HttpOnly, and SameSite=Lax.
- All protected-route decisions remain server-side even when navigation is role-aware.

## Break-glass super administrator

The local break-glass account is an emergency recovery control, not a daily account. Until a dedicated `is_break_glass` field and operating workflow are added, every local `is_super_admin` account receives the stricter no-persistent-session behavior.

Required future controls are documented in `docs/authentication/BREAK_GLASS_RUNBOOK.md`. The account must remain independent of LDAP/SSO, be protected from removal when it is the final recovery administrator, use a separately managed high-entropy password, and produce high-visibility audit events when used.

## Refactor review

Current modules are cohesive and below the practical review thresholds. The previous provider parsing in `services.py` was separated into `providers/registry.py`; session mutation was separated into `session.py`; and login alerts/provider state were split into traceable partials. `routes.py` now remains focused on HTTP orchestration.

No larger split is currently justified. Re-review when:

- a Python module exceeds roughly 300–400 lines;
- a route or service function exceeds roughly 60–80 lines;
- provider-specific branching appears in `routes.py`;
- LDAP/SSO introduces callbacks, state/nonce verification, certificate handling, or mapping logic;
- password policy, lockout, and recovery become independent workflows.

## Documentation set

- `docs/authentication/AUTHENTICATION_ARCHITECTURE.md`
- `docs/authentication/AUTHENTICATION_SECURITY.md`
- `docs/authentication/AUTHENTICATION_FLOWS.md`
- `docs/authentication/AUTHENTICATION_DATA_MODEL.md`
- `docs/authentication/BREAK_GLASS_RUNBOOK.md`
- `docs/authentication/PROVIDER_INTEGRATION_CONTRACT.md`
- `docs/authentication/AUTHENTICATION_TEST_PLAN.md`

## Known implementation gaps before external providers

- Durable account lockout and failed-attempt counters are not yet stored on the user/account model; the current limiter protects the HTTP endpoint.
- A dedicated `is_break_glass` marker and break-glass usage event classification are not yet present.
- LDAP and SSO adapters are declarations only.
- External identity projection and group/claim role mapping belong to the next RBAC/role-mapping design stage.
- Password expiry, password history, forced rotation, and recovery codes are not implemented.

## LDAP activation phase

LDAP authentication is now an active adapter for administratively projected users. The adapter resolves an `ExternalIdentityLink`, checks that its provider is enabled, verifies the user by LDAP bind, then returns the linked KAORI `User`. User lifecycle remains authoritative in KAORI.

OIDC configuration fields are reserved but OIDC cannot yet be enabled. JIT provisioning is blocked until RBAC role mapping is implemented.

See `docs/authentication/EXTERNAL_IDENTITY_FLOW.md`.

## Google and GitHub SSO

Browser SSO adapters are implemented in `app/auth/providers/oauth.py`, while projection and admission policy remain in `app/auth/sso.py`. Google uses OIDC and GitHub uses OAuth App semantics. See `docs/authentication/GOOGLE_GITHUB_SSO.md`.


## Unified Activity Audit Log

Every completed login attempt and every user-initiated logout is recorded under the canonical `authentication` event type in Activity Audit Log. The event metadata captures the sign-in/sign-out action, provider, result, reason code, attempted username, IP address, browser, operating system, device class, and raw user-agent. Failed attempts that cannot be mapped to a KAORI user are stored with a nullable actor and presented as unauthenticated requests.

Authentication events are audit-only records and are marked reviewed when written, so routine login/logout activity does not create unread personal notification-center items. Legacy `AuthLoginEvent` persistence remains temporarily for backward compatibility; migration `20260717_auth_activity` backfills existing Login Activity rows into the unified audit stream.
