# Ansible SSH Access References — Review-Only Contract v1

**Authority:** #556 Infrastructure Automation, #4796 Ansible execution, #5155/5161 canonical host inventory, #5162 SSH/credential admission, #714 Secrets & PKI, #4799 dedicated worker. Downstream immutable Plan #5163/#4800 and non-production mutation #4801 remain separately authorized.

## Ownership and first implementation

The first #5162 source slice in `app/infrastructure_automation/host_access_reference.py` is a **pure read-only reference classifier**, not credential/SSH admission. It interprets only a canonical active non-production Ansible `IntegrationInstance` with source-checked immutable Git pin, an immutable EE digest reference, one KAORI host asset identity, existing `SecretIdentity` + `SecretProviderRepresentation` metadata, and an opaque public host-key digest. Secret values remain owned by the external provider; KAORI owns only normalized evidence/correlation.

It refuses cross-provider, wrong secret identity, unknown/revoked representation, missing version, unknown host/invalid scope/source/EE or absent host-key reference. A structurally valid record is labeled `references_recorded`, **never** `ready_for_execution`. Merely providing a Vault representation ID or host-key digest does not prove key usability, SSH host-key trust, access scope, network reachability, privilege escalation or an admitted automation worker. The function does not accept worker-provided approval flags.

The operator-facing committed summary is only a deterministic fingerprint, generic reason/status, and two Boolean `*_reference_recorded` indicators. It always exposes `ssh_trust_verified=false`, `privileged_identity_verified=false`, `execution_authorized=false`; it does not serialize host IDs, IPs, secret identities, Vault paths or raw key material. The fingerprint is **not a signature or authorization token**. A changed source, EE, secret version or host-key reference changes the fingerprint and invalidates any prior review correlation.

## Security separation / remaining children

1. #5161: after asset model/namespace admission, read only permission-scoped Compute/VM/Bare-Metal host identity from approved KAORI persistence. Do not use Kubernetes `NodeInventory` as pre-provision SSH inventory.
2. #5162 follow-up: use existing Secrets & PKI scope permissions and authoritative provider secret metadata, not user-submitted model instances. Require actual approved secret role/type, current secret version, host↔secret binding and secret-provider verification.
3. #4799/#5066: add isolated worker trust, SSH known-host identity, remote host-key verification and sudo/privilege proof from a non-production disposable target under exact Git SHA and signed EE digest. No SSH from normal GET/Flask and no credential values in Celery/JobExecution.
4. #5163/#4800: persist only a canonical immutable, time-bounded Plan/JobExecution and validate freshness/worker admission/source/secret/inventory at every execution boundary.
5. #4801: independent maker/checker + change window and target lock, Ansible Runner/Kubespray native execution, independent Kubernetes API readback. Production enablement and upgrades remain HOLD.

## Validations

Ruff/check-format, focused pytest, Pyright, Developer Check, Full Admission and Security/DAST on exact head; independent review and staged human non-production UAT separately. No schema migration, route, UI action, secret write, arbitrary Ansible inventory, authorization broadening, live SSH or cluster mutation is delivered by this small foundational slice.
