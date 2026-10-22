# HashiCorp Vault — Secrets & PKI provider (HV-01 / #2585)

## Authority

Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault → Instance.

Vault controls Secret values, native ACLs, authentication, issuers and PKI keys.
KAORI owns approved integration registration, AppRole credential encryption,
bounded read-only observation, canonical capability/readiness evidence and job/audit history.
The **separate** operational Secrets & PKI Dashboard, safe KV v2 inventory,
consumer correlation, PKI evidence, Metrics/Alert Source bindings, Analytics, and
Intelligence are implemented under HV-02–HV-15. They are NOT implied by this foundation.

## Secure setup

In both DevContainer web and validation/runtime worker environment:

```bash
INTEGRATION_CREDENTIAL_KEY=<existing approved Fernet encryption key>
INTEGRATION_VAULT_ALLOWED_ORIGINS=https://vault.internal.example:8200
INTEGRATION_VAULT_CA_BUNDLE=/etc/ssl/approved/vault-root-ca.pem  # optional if system trusted
```

Do not commit real values or CA private material. The origins list contains exact HTTPS
origins and is fail-closed when missing. HTTPS verification is always enabled, proxy/netrc
inheritance and redirects are disabled, and a short request timeout is enforced.
Approved origins alone are not DNS pinning; environment egress rules and DNS
restrictions must independently constrain outbound Vault access.

Use a non-root, least-privilege AppRole for the KAORI integration. A reusable
appropriately scoped SecretID is necessary for Test Connection and subsequent worker
Full Validation; an AppRole configured with a one-use SecretID will be consumed at
first login. Rotate the AppRole SecretID through the approved operational process.
Vault client tokens live in worker process memory for the probe and are not persisted
in IntegrationInstance, JobExecution, runtime snapshots, or logs.

Test Connection checks Vault health, AppRole login and lookup-self. It does not
mark the provider ready. Full Validation is queued through the existing
integration-validation worker; it checks the token and optional sys/mounts
metadata capability. A missing sys/mounts permission is an independently
qualified capability gap, not proof that Vault API is unavailable. Runtime Refresh
uses sys/health only and distinguishes active, standby, performance standby,
sealed, uninitialized, DR secondary, and unavailable states.

No Secret value, KV v2 data endpoint, private key, token issue/revoke or policy
write is permitted through HV-01.

## DevContainer review

After pulling `kaori/review/staging-uat` once changes are integrated:

```bash
# Follow the repository's standard .env / development database initialization.
bash scripts/init_db.sh --bootstrap-admin
python -m pytest tests/integrations/test_vault_provider.py -q
python -m ruff check app/models/vault.py app/integrations/secrets_management tests/integrations/test_vault_provider.py
```

Open Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault;
register an approved Vault connection, then exercise Test Connection,
Full Validation, Runtime Refresh and edit/readiness behavior. Verify actual
PostgreSQL/Alembic migration, browser light/dark and responsive flow, worker
queues, least-privilege 403 response and CA/SSRF negatives. These focused steps
do not substitute Developer Check, Full Admission, staging UAT or human acceptance.

If no real Vault instance is configured, do not claim connectivity, inventory,
Analytics or Intelligence has passed UAT.
