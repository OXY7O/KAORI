# Authentication test scope

The authentication suite protects provider-neutral behavior rather than only rendered UI.

- `test_provider_catalog.py`: canonical provider type/family registry.
- `test_authentication_service.py`: local authority and external credential fallback.
- `test_database_provider.py`: local password verification and database-failure normalization.
- `test_ldap_provider.py`: credential rejection versus provider outage and TLS behavior.
- `test_browser_sso_registry.py`: registered browser strategies, state hashing, and authorization URLs.
- `test_provider_configuration.py`: provider-specific configuration projection and field cleanup.
- `test_identity_source_mapping.py`: concrete SSO source mapping and password ownership.
- `test_session_policy.py`: session rotation and break-glass remember-me policy.
- `test_readiness.py`: required authentication schema and database outage handling.
- `test_sso_identity_resolution.py`: SSO registry lookup, link synchronization, and database-failure normalization.
- `test_ldap_auth_adapter.py`: multi-link LDAP authentication, provider outages, and inactive accounts.
- `test_auth_architecture_contract.py`: domain ownership and retired compatibility boundaries.

Run the domain gate with:

```bash
pytest -q tests/auth
```

Run coverage for the domain with:

```bash
pytest -q tests/auth --cov=app.auth --cov=app.users.identity --cov-report=term-missing
```
