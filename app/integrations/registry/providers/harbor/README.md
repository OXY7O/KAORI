# Harbor Registry Provider

Harbor is the first provider implementation for the KAORI **Registry** integration domain.

## Authority boundary

Harbor remains authoritative for projects, repositories, artifacts, vulnerability data,
retention/immutability policy, replication, webhooks, users, robot accounts, and native
Registry state. This foundation does not expose destructive or provider-policy mutation.

KAORI owns normalized provider registration, credential handling, compatibility resolution,
committed Full Validation evidence, lightweight runtime observation, governance context,
correlation-ready identity, and audit history.

## Workspace flow

```text
Integrations → Registry → Harbor
                    │
                    ├── Register Connection
                    │     └── Test Connection
                    │
                    └── Connection Detail
                          ├── Configuration
                          ├── Validation & Capabilities
                          └── Runtime & History
```

`Test Connection` proves Harbor identity and endpoint reachability only. The signed proof is
bound to the submitting user and effective registration fields and expires after ten minutes.
Changing any bound field invalidates the proof.

`Full Validation` is the authority for detected Harbor version, compatibility, required
read-oriented API capabilities, and provider readiness. `Runtime Refresh` is deliberately
separate and updates lightweight health observations without rebuilding compatibility or
capability evidence.

## Local devcontainer validation

Use the repository's canonical Dev Container flow; Harbor does not require a separate local
service or a provider-specific bootstrap path.

Before rebuilding the container, copy `.env.example` to `.env` and set normal development
secrets. Basic Authentication connections additionally require
`INTEGRATION_CREDENTIAL_KEY`; Anonymous read-only connections do not persist a password.

Inside the Dev Container:

```bash
bash scripts/init_db.sh --bootstrap-admin
python -m pytest \
  tests/integrations/test_harbor_client.py \
  tests/integrations/test_harbor_compatibility_contract.py \
  tests/integrations/test_harbor_readiness.py \
  tests/integrations/test_harbor_registration_proof.py \
  tests/contracts/integrations/test_harbor_provider_foundation_contract.py \
  tests/contracts/integrations/test_harbor_provider_workspace_contract.py \
  -q
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

Then open `http://localhost:5000` and follow
`Integrations → Registry → Harbor`. Exercise the boundary in order: Test Connection,
Register Connection, Full Validation, then Runtime Refresh. Full Validation expects the
credential to see at least one Harbor project so KAORI can prove the project-scoped
repository-list capability. The probe remains GET-only and does not mutate Harbor.

These are focused local checks only. They do not replace Developer Check, Full Admission,
staging UAT, or the governed promotion flow.

## Foundation exclusions

Artifact inventory, vulnerability findings, webhook workflows, cross-domain Registry
correlation, consumer bindings, and operational Registry mutation are outside issue #884.
Those surfaces must not be inferred from this provider foundation.
