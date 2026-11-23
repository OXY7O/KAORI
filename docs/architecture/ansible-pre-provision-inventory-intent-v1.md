# KAORI Pre-Provision Host Inventory Intent — Review Contract v1

**Authority:** #556 → #4796 → #5155; depends on #4799, #4800, and independently approved #4801. Follow existing IntegrationInstance, IntegrationBinding, Kubernetes Cluster/NodeInventory and canonical JobExecution authorities.

## Decision

KAORI manages the **canonical pre-provision host asset identities and approved inventory intent**. Ansible remains the authoritative interpreter of native inventory, groups, connection variables and task execution. Git `OXY7O/kaori-operations` owns reviewed Kubespray automation definitions. Kubernetes API `Cluster`/`NodeInventory` remains authoritative for operational observations **after provisioning**. Never use post-provision `NodeInventory` as the pre-provision SSH target repository.

The pure `app/infrastructure_automation/inventory_intent.py` policy is the first **non-mutating review-only** validation and redacted fingerprint seam. It has no database migration, no input route, no SSH/Ansible call and **does not yet implement host registration or real inventory snapshot persistence**. A future repository adapter must construct its input only from permission-scoped, committed KAORI host records, never browser JSON/YAML. Additional bounded child workstreams are required for actual DB host ownership, registration UI, SSH trust, independent source/EE attestation and worker execution.

## Reviewed pilot envelope

- Existing Linux VM/bare-metal in explicit non-production environment.
- Three distinct private IPv4 host endpoints, one control-plane and two workers; validated asset IDs, SSH port and role.
- Opaque *reference strings only* for SSH credential authority and trusted host-key evidence; a reference **is not proof of admission**.
- Immutable Git source SHA and Execution Environment `sha256:` digest, bound to canonical Ansible IntegrationInstance identity.
- Fingerprint changes when host ID/IP/port/role, credential/host-key references, environment, source or EE changes; deterministic regardless of record order.
- Committed review summary contains **only** fingerprint, aggregate role counts, status/reason and always `execution_authorized=false`. It deliberately omits endpoints, hostnames, SSH references and secret values.

An SHA-256 fingerprint is a correlation checksum, **not a cryptographic signature, approved Plan, credential, or authorization token**. `review_only` does not qualify remote host identity/credentials. A future mutating Run under #4801 must independently compare canonical inventory generation, SSH host-key trust, secret authority, source/EE signatures, maker/checker approval and maintenance window, exact target locks and API read-back before making changes.

## Next issue workstreams

1. Introduce/reuse canonical host persistence and asset ownership after inspecting existing source-of-truth; migration and DB negative contracts under #5155.
2. Add guarded host registry, inventory role/group assignments and preview UI under existing Infrastructure Automation #5157, default page 5 and reused Violet/HTMX components; no raw key entry.
3. Add source- and identity-scoped credential and host-key attestation records via approved Secrets & PKI ownership (#4799). Never persist secret material in source, broker or evidence.
4. Materialize review fingerprints into canonical JobExecution/Plan evidence, with freshness, invalidation on any field change and ownership correlation (#4800).
5. Only after explicit isolated non-production authorization, enable signed runner inventory dispatch/independent Kubernetes verification under #4801. Scale/upgrade/recovery remain independently governed (#4895–#4897).

## Validation and acceptance

- Focused source/negative tests: `tests/integrations/test_kubespray_inventory_intent_5155.py`.
- Exact-head existing Ruff/check-format, Pyright, pytest, Developer Check/Full Admission.
- Later persistence, shared UI, real SSH readback, browser Visual QA and Human Acceptance must **not** be marked complete from a pure contract test.
- No parallel provider, generic Ansible command runner, arbitrary inventory YAML submission, unapproved production mutation, or direct main branch change.
