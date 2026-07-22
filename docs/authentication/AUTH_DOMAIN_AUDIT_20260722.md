# Authentication Domain Audit — 2026-07-22

## Scope

Review of the Local Database, LDAP / Active Directory, and browser SSO foundations before direct operator testing. The audit covered domain ownership, provider extension points, credential authority, external identity mapping, session and callback controls, rate limiting, schema readiness, provider administration boundaries, and non-UI test coverage.

## Result

The Auth domain now has two explicit protocol families:

- **credential providers** through `CredentialAuthProvider` and `CredentialProviderRegistry`;
- **browser SSO providers** through `BrowserSsoProvider` and the explicit browser strategy registry.

`app/auth` has no import dependency on `app/users`. User Management maps WTForms into an Auth-owned DTO and consumes Auth services. Provider-specific protocol branches are absent from the login and provider-administration routes.

## Findings and Changes

### 1. Provider architecture was split into unrelated paths

Database and LDAP used a credential registry while Google/GitHub SSO used direct branching in a combined OAuth module and routes.

**Change:** added the canonical provider catalog, `CredentialProviderRegistry`, and an explicit browser SSO registry. Google and GitHub now use dedicated strategy modules.

### 2. LDAP protocol ownership was inverted

Authentication imported LDAP protocol behavior from `app/users/providers/ldap.py`.

**Change:** LDAP connection, TLS, search, service bind, and user bind now live in `app/auth/providers/ldap.py`. The obsolete Users provider package was removed.

### 3. Auth still depended on a Users WTForms class

Provider model projection had been moved to Auth but its function accepted `IdentityProviderForm`, leaving the core domain coupled to the administration UI.

**Change:** introduced `IdentityProviderConfiguration` as an Auth-owned DTO. `app/users/provider_forms.py` performs the UI-to-domain mapping. Static dependency inspection now reports zero Auth-to-Users imports.

### 4. SSO family filtering was incorrect

The User Management filter accepted `sso` but queried `users.auth_source = 'sso'`, while stored values are `google_oidc` and `github_oauth`.

**Change:** family filters now resolve to concrete provider types from the canonical catalog.

### 5. Unknown identity sources could inherit Database password ownership

Unknown source values fell back to the Database identity definition.

**Change:** unknown values fail closed and never permit KAORI password management.

### 6. LDAP outages were indistinguishable from invalid credentials

The LDAP client converted every bind failure into `False`.

**Change:** LDAP `invalidCredentials` returns `False`; connection, TLS, and operational bind failures raise a normalized provider error.

### 7. LDAP provider selection was not multi-provider safe

Only the first matching external username was used, with case-sensitive matching.

**Change:** matching is case-insensitive, enabled LDAP links are ordered deterministically, and matching links are attempted until one succeeds.

### 8. SSO implementation was difficult to extend

Google and GitHub branches were concentrated in `providers/oauth.py`.

**Change:** dedicated `google_oidc.py` and `github_oauth.py` strategies implement the shared browser contract. The combined module was removed.

### 9. SSO provider lookup was not type-constrained

An enabled LDAP provider key could be loaded by the SSO route before strategy rejection.

**Change:** SSO lookup now filters to concrete provider types registered for browser flow.

### 10. SSO callback validation was route-local and brittle

Provider ID, state, timestamp conversion, and TTL checks were implemented inline; malformed session values could raise conversion errors.

**Change:** `sso_flow_is_valid()` is a pure fail-closed function with direct tests for mismatch, expiry, future timestamp, and malformed values.

### 11. SSO registry/database errors could return HTTP 500

Provider lookup and identity-link operations were not consistently normalized.

**Change:** storage failures rollback and return safe `database_unavailable` outcomes.

### 12. Authentication readiness omitted required tables

Readiness did not require `external_identity_links` or `notifications`, although both are touched during login.

**Change:** both tables are part of the authentication readiness contract.

### 13. Successful audit events could be written before login completion

Success could be recorded before login metadata and session establishment completed.

**Change:** success is recorded only after metadata commit and session establishment. Commit failures become `database_unavailable`.

### 14. SSO flow controls were partially hardcoded

SSO rate limit and flow lifetime lacked explicit runtime configuration.

**Change:** added `AUTH_SSO_RATE_LIMIT`, `AUTH_SSO_RATE_LIMIT_MESSAGE`, bounded `AUTH_SSO_FLOW_TTL_SECONDS`, and documented them in both environment templates.

### 15. Optional limiter fallback silently disabled a security control

`app/extensions/limiter.py` contained a no-op implementation when Flask-Limiter was unavailable even though the dependency is locked in `requirements/base.txt`.

**Change:** removed the fallback. A broken dependency installation now fails fast instead of booting KAORI without authentication rate limiting.

### 16. Provider key format was not canonical

Provider keys could contain spaces or path-like characters even though they are used in callback URLs.

**Change:** provider keys are normalized to lowercase and restricted to letters, numbers, hyphens, and underscores through a shared validator with direct tests.

### 17. ORM provider predicates duplicated the catalog

`IdentityProvider.is_ldap`, `is_oidc`, and `is_sso` hardcoded provider sets in the model.

**Change:** removed the unused predicates. Provider classification now has one authority in `providers/catalog.py`.

### 18. Retired provider configuration remained in environment templates

`AUTH_ADDITIONAL_PROVIDERS` had been removed from application config but remained in `.env.example`.

**Change:** removed it from development and production templates and added an architecture contract preventing reintroduction.

## New Function Test Gate

`tests/auth/` covers:

- provider catalog, family mapping, and catalog/registry consistency;
- credential orchestration and Local Database authority;
- Database provider outcomes and storage errors;
- LDAP URI/TLS/search/bind behavior and adapter fallback;
- browser strategy authorization URLs and state/TTL validation;
- SSO provider lookup, link synchronization, JIT admission, conflicts, and storage failures;
- provider configuration DTO projection and key normalization;
- identity-source password ownership;
- session rotation and super-admin remember-me policy;
- authentication schema readiness;
- domain ownership, dependency direction, required limiter, and retired boundaries.

## Validation Performed in Audit Sandbox

- Python compile of `app` and `tests`: passed.
- Local Auth/User import-path scan: zero missing local imports.
- Static Auth-to-Users dependency scan: zero imports.
- Dependency-free project tests: **426 passed**.
- Focused Auth architecture tests: **7 passed**.
- Migration changes: none.

The complete runtime suite requires the KAORI dev-container dependencies (`Flask`, Flask extensions, `ldap3`, and Google auth libraries), which were unavailable in the audit sandbox.

## Direct Testing Gate

```bash
flask db current
flask db upgrade
pytest -q tests/auth
pytest -q tests/auth --cov=app.auth --cov=app.users.identity --cov-report=term-missing
```

Then execute the Local Database, LDAP, Google OIDC, and GitHub OAuth manual matrix in the patch validation guide.
