# Kubernetes Internal Certificates — Native Renewal Ownership and Read-only Collection

> **Approved architecture decision, 2026-11-12 — supersedes the historical KAORI renewal blueprint.** Authority #4441 / #4445; source contract #4442, collection #4443, operational UI #4444, Ansible capability #556 and Kubernetes governance #757. This path is retained for existing documentation links. **KAORI does not orchestrate or execute certificate renewal, CA rotation or CSR approval.**

## 1. Product decision and ownership

**Internal Certificates is a read-only collection, inventory, expiry monitoring and governance capability.** KAORI collects qualified non-secret metadata through an approved authoritative source, validates/normalizes it, commits evidence, correlates owner and source, and renders the latest recorded posture. Native Kubernetes/distribution tooling, managed providers or external PKI systems retain all certificate lifecycle operations.

- **Kubeadm/control-plane and etcd certificates:** owning infrastructure team uses the verified cluster-native `kubeadm` and platform maintenance procedure **outside KAORI**. KAORI never dispatches `kubeadm certs renew`.
- **Managed Kubernetes:** the managed provider owns supported control-plane PKI lifecycle; KAORI displays only documented provider-exposed facts and links to the owner's operating procedure.
- **External CA / Vault / custom PKI:** the signing/PKI provider and its owner remain authoritative; KAORI stores lifecycle metadata and an owner handoff, never signing material.
- **Kubelet client and serving certificates:** cluster-native rotation and approved CSR processes remain external. A CSR alone is not evidence of an installed certificate's validity; KAORI does not approve CSRs.
- **CA certificates:** any CA/key/trust rotation is a separate external change-controlled platform procedure, not a KAORI action.

The previous proposal for KAORI `Request Renewal`, `Rotate All`, preflight/approval/execute controls, Ansible renewal playbooks or lifecycle mutation schema is **withdrawn** as an implementation target. Preserving historical discussion does not confer permission to implement those actions. A future change to this boundary requires an explicit new architecture decision, bounded issue, security review and human approval.

## 2. Committed read-only architecture

```text
KAORI scheduled/on-demand evidence collection (#4443, future)
  -> Source capability resolution by cluster/provider/instance
  -> Authorized Ansible / approved host collector, when admitted
     OR documented provider API / supplementary Kubernetes API
  -> Strict versioned metadata adapter + validation
  -> Idempotent committed PKI batch + inventory + Activity Audit
  -> Kubernetes > Governance > Internal Certificates read model (#4444)
     Source, freshness, coverage, certificate identity, issuer,
     source-reported NotAfter, expiration posture, owner and native handoff
```

**Ansible executes read-only acquisition only**, never certificate renewal. Use the existing #556 orchestration integration when operational; do not add direct SSH, unrestricted shell, control-plane mounts or privileged Kubernetes API execution from a page or KAORI worker. Normal UI GET reads committed KAORI state, not live provider calls.

The current `flask prepare-internal-pki` + `flask import-internal-pki` manual operator-attested path remains a restricted **non-production UAT/controlled fallback**. It proves normalization and persistence, **not** automated collection, installed certificate use, CA trust, or full-node coverage. #4443 is the separate authority to implement scheduled collection after source owner/identity and runner compatibility are approved.

## 3. Collection support and evidence boundaries

| Source family | Read-only evidence source | Coverage / provenance rule | Lifecycle owner |
| --- | --- | --- | --- |
| Self-managed kubeadm control-plane leaf / local etcd | Version-verified `kubeadm certs check-expiration -o json` on each authorized control-plane host | Exact node, tool/schema version, leaf + CA linkage, collection time and partial/full node scope | Cluster operations team using native kubeadm / etcd runbook |
| Kubelet installed client/serving cert | Approved node-local certificate evidence when available | Distinguish installed evidence from Kubernetes CSR observation | Kubelet/native signer and owning cluster team |
| Kubernetes CSR | RBAC-scoped Kubernetes API | Supplementary request/approval state; not installed expiry | Approved signer / CSR controller |
| Managed control plane (GKE/EKS/AKS/OKE) | Official provider API **only for exposed fields** | Provider-managed/Unavailable when active cert expiry is not exposed | Cloud provider |
| External CA / custom distribution | Approved external PKI source/API | External authority and owner, no key material | External PKI operator |
| Unsupported/unknown source | No invented values | Not Collected/Unsupported/Unknown, not Healthy | Cluster owner |

Strict metadata-only validation must reject unexpected keys, credentials, PEM, private keys, raw kubeconfig, arbitrary host stdout and unsupported versions. Never persist any CA signing key, CSR private key, provider credential or raw privileged output in KAORI DB, Activity Audit, job logs or GitHub.

Expected coverage is derived from independently verified cluster/control-plane topology, not a successful response from one node. A failed run must **not** delete previous committed evidence; retain the old snapshot, separately expose failure/freshness and maintain source-qualified identities. Atomic commit, idempotent batches, bounded output/timeouts and read-side cluster/RBAC isolation are mandatory.

## 4. Expiration monitoring and operational handoff

The Registry may show source-reported `not_after`, issuer, leaf/CA, owner, externally-managed state, collection provenance and evidence freshness. Display classifications (expired/critical/renewal-window/outside-window/stale) are monitoring labels, **not** a renewal authorization or proof the certificate is active. Never report empty or stale evidence as verified Healthy.

When operator action may be required:
1. KAORI identifies the affected cluster, node, component, expiry, evidence age and qualified native/PKI owner, without presenting mutation controls.
2. The operator uses the **authoritative external platform runbook**, change/maintenance approval, backup/recovery planning and native tool/API outside KAORI.
3. After the external change, KAORI collects a new read-only evidence batch through an approved source and compares source-reported post-change validity. Provider health/trust verification remains independently owned and must not be inferred from a new expiry date.
4. KAORI can correlate the external change reference, before/after evidence and Activity Audit without duplicating execution or storing secret material.

For a high-availability control plane, the external owner must consider one-node-at-a-time operations, control-plane and etcd quorum, static-pod restarts, backup/restore and rollback through their own approved procedure. This document is **not** a kubeadm renewal procedure and grants no execution authority.

## 5. Implementation and acceptance boundaries

- **#4442**: verify distribution, PKI owner, source API/command/schema/version, per-node coverage, approved execution identity and safe output before admitting a source.
- **#4461 / #4480**: existing strict manually imported UAT metadata and source-specific adapter, without any host automation.
- **#4443**: future bounded child implementation(s) for collection scheduling, existing Ansible/provider executor integration, safe node reads, failure/retry, normalization, evidence commit and tests; **read-only only**.
- **#4444 / #4465**: committed evidence-backed UI, correct breadcrumb, permissions, default 5-row pagination, light/dark/mobile, native owner guidance.
- **#4445**: product boundary and native renewal handoff authority; no KAORI renewal implementation workstream.

Tests must include secret rejection, unqualified provider, unauthorized collection/cluster access, outdated/mismatched schema, failed run retaining prior evidence, partial HA scope, duplicate/idempotent batch, stale/expired distinction, UI no-renew controls and cross-domain regression. Use existing `ruff`, `pyright`, `djlint`, `pytest`, Playwright and `verify_*` gates. Provider evidence and Human UAT are mandatory for each approved collection source. Do not claim CI or UAT PASS without execution on the exact candidate.

**Official admission and all host mutation remain governed by the existing KAORI workflow.** Updating this monitoring-only decision never authorizes a new runner, production access or external PKI change.

## References

- [Internal Certificates Source & Support Contract](KUBERNETES_INTERNAL_CERTIFICATES_SOURCE_CONTRACT.md)
- [Operator-Attested Metadata Import Runbook](KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md)
- #4441 foundation; #4442 discovery; #4443 collector; #4444 workspace; #4445 lifecycle ownership; #556 Ansible; #757 Governance
