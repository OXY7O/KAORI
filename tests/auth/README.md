# Authentication functional test gate

`tests/auth` contains permanent tests that validate authentication behavior. It is the domain gate for Local Database, LDAP, Google OIDC, GitHub OAuth, session policy, readiness, and identity resolution.

This folder must not contain migration graph checks, retired-file checks, temporary reproductions, or UI snapshot assertions.

## Functional coverage

- `test_authentication_service.py`: local authority and external credential fallback.
- `test_authentication_audit.py`: authentication event projection, safe metadata, and non-blocking audit persistence.
- `test_database_provider.py`: local password verification, inactive accounts, timing-safe unknown-user path, and database failure normalization.
- `test_ldap_provider.py`: LDAP transport policy, bind behavior, TLS/StartTLS, invalid credentials, and provider outage behavior.
- `test_ldap_auth_adapter.py`: multi-provider LDAP link resolution and inactive-account handling.
- `test_browser_sso_registry.py`: browser strategy registry, authorization URLs, state hashing, and callback TTL validation.
- `test_sso_provider_exchange.py`: Google and GitHub token/profile projection behavior.
- `test_sso_identity_resolution.py`: identity-link synchronization, JIT admission, and database failure normalization.
- `test_provider_catalog.py`: canonical provider family/type/label behavior.
- `test_provider_configuration.py`: provider-specific configuration projection and field cleanup.
- `test_identity_source_mapping.py`: source-family mapping and password ownership.
- `test_session_policy.py`: session rotation and break-glass remember-me policy.
- `test_login_completion.py`: login metadata transaction boundary before session establishment.
- `test_readiness.py`: authentication persistence readiness and database outage behavior.

## Commands

Run the functional Auth gate:

```bash
pytest -q tests/auth -m functional
```

Run Auth coverage:

```bash
pytest -q tests/auth -m functional \
  --cov=app.auth \
  --cov=app.users.identity \
  --cov-report=term-missing
```

Architecture and retired-boundary checks are separate:

```bash
pytest -q tests/contracts/auth -m contract
```

Migration tests belong in `tests/migrations`; temporary diagnostic tests belong in `tests/debug` and must be replaced by a permanent functional regression test before a defect is closed.
