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

## Foundation exclusions

Artifact inventory, vulnerability findings, webhook workflows, cross-domain Registry
correlation, consumer bindings, and operational Registry mutation are outside issue #884.
Those surfaces must not be inferred from this provider foundation.
