# Kubernetes Internal Certificates — Source and Support Contract

> **Status:** Proposed source contract, 2026-11-12; source support is **not yet verified** against registered production clusters. Authority: #4441 / discovery #4442; subsequent collector #4443 and workspace #4444. **No collection, renewal, menu or mutation is authorized by this document.**

## 1. Domain boundary

`Kubernetes → Governance → Internal Certificates` is separate from the existing `TLS Certificates` capability. Existing TLS collection covers Kubernetes TLS Secrets, Ingress declared-host relationships and a worker-committed inventory; it **cannot** determine apiserver, etcd, front-proxy, controller-manager, scheduler or kubelet active PKI certificate expiry.

KAORI owns the normalized, **committed** evidence and governance context; external cluster PKI tools, managed providers or external CAs remain authoritative for collection and lifecycle. UI reads KAORI committed state only. Do not duplicate a CA, invent expiration dates, or expose private keys, kubeconfig material or unredacted command output in DB, logs, jobs, UI or audit.

## 2. Confirmed implementation inspection (2026-11-12)

- `app/models/cluster.py` defines `Cluster` identity, environment, description, status, node count and connection association. It does **not** declare a certified cluster distribution, Kubernetes PKI authority, kubeadm installation, host-execution identity, external CA ownership or a read-only PKI collection capability. A cluster being Connected **is not** evidence that kubeadm or SSH is available.
- `app/kubernetes/governance/tls_certificates/collector.py` reads Kubernetes TLS Secret/Ingress content through the registered container-orchestrator provider and commits TLS-specific evidence. It does not read control-plane host PKI. Never infer internal PKI validity from those rows.
- Foundation #556 establishes **KAORI orchestrates; Ansible executes; Git defines; Evidence proves**, but that does not itself confirm a permissioned host-runner or a supported kubeadm job template exists for a given cluster.
- This is a **source discovery decision record**, not an assertion about which clusters the organization actually operates. Per-cluster support remains **Unknown / Not Verified** until owner-reviewed evidence exists.

## 3. Source/authority and feasibility matrix

| Target | Preferred authoritative source | What it can prove | Precondition | Rotation authority | Initial support |
|---|---|---|---|---|---|
| kubeadm control-plane leaf (apiserver, apiserver-kubelet-client, scheduler/controller-manager kubeconfig, front-proxy-client) | `kubeadm certs check-expiration -o json` on each authorized control-plane host **when supported by installed kubeadm version** | Local file/kubeconfig certificate expiry, CA association, external management flag | Distribution and version confirmed; approved host identity; read-only command policy | kubeadm, external signer where applicable | **Conditional; unverified** |
| kubeadm etcd peer/server/client | Same per-node kubeadm source for locally managed etcd PKI; external etcd needs its own owner-approved source | Local etcd cert expiry, not etcd quorum health | etcd topology and per-host authority known | kubeadm or owner of external etcd | **Conditional; unverified** |
| Kubernetes CA, etcd CA, front-proxy CA | kubeadm CA expiration report, or external CA/PKI provider metadata | Public certificate validity, not signing-key custody or CA rotation safety | CA issuer/owner verified | External/cluster PKI change procedure; **no automatic CA rotation** | **Monitoring conditional; mutation excluded** |
| kubelet client installed cert | Authorized node-local certificate parse or supported agent/owner evidence | **Installed** client certificate expiry on a node | Trusted host evidence source and node identity | Kubelet automatic rotation, external signer if configured | **Not yet collectible** |
| kubelet client CSR | `certificates.k8s.io` API, scoped/authorized observation | CSR signer/requestor/conditions, **not** installed certificate validity | CSR read RBAC and identity normalization | Kubernetes signer/approval controller | **Separate supplementary evidence** |
| kubelet serving cert / CSR | Approved node-local active cert source **plus** CSR state | Active serving cert or pending approval, separately | `serverTLSBootstrap` / signer policy and node ownership known | Verified signer / explicitly approved CSR workflow | **Conditional; no default auto-approval** |
| Managed control plane (GKE/EKS/AKS/OKE, etc.) | Provider's documented certificate lifecycle/status API if exposed | Only provider-reported fields | Provider identity, cloud credentials, documented API | Provider-managed | **Provider-managed / visibility unavailable until verified** |
| External CA / custom distro | CA service, approved PKI interface or operator attestation | External validity/renewal ownership | External signer/CA and data contract confirmed | External authority | **Manual/external handoff until verified** |

A service-account Kubernetes API call **does not** expose kubeadm's full host-local PKI by default. `kubectl get csr` does **not** establish the expiry of the currently installed kubelet certificate.

Reference: [Kubernetes kubeadm certificate management](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/), [kubeadm check-expiration CLI](https://kubernetes.io/docs/reference/setup-tools/kubeadm/generated/kubeadm_certs/kubeadm_certs_check-expiration/), [kubelet rotation](https://kubernetes.io/docs/tasks/tls/certificate-rotation/).

## 4. Discovery checklist per actual registered cluster

For every `Cluster.id` under its existing access scope, record only owner-confirmed, non-secret facts:

1. **Identity:** internal cluster ID, environment, operational owner, multi-control-plane topology, Kubernetes version, distribution and management model. Missing distribution is **Unknown**, never infer kubeadm from node status.
2. **PKI authority:** kubeadm-managed, provider-managed, external CA, custom tool or unknown; distinguish *control-plane leaf*, *etcd*, *CA*, *kubelet client* and *kubelet serving* ownership.
3. **Execution interface:** existing authorized read-only identity/approved runner; exact host/node and command allowlist. Never establish new unrestricted SSH or privileged shell access as a side effect of discovery.
4. **Compatibility:** confirm `kubeadm version` and supported `certs check-expiration --output=json|yaml`; capture schema version and **field inventory only**. Structured output must be tested against the target installed version; never parse locale-sensitive text tables as production authority.
5. **Coverage:** enumerate expected control-plane node IDs and source-reported identities; distinguish full vs partial node coverage and local vs external etcd.
6. **Failure handling:** missing command, insufficient permission, unsupported distribution, schema mismatch, source error, stale snapshot or no rows all remain distinct evidence states; none becomes `Healthy`.
7. **Approval:** operations infrastructure owner approves the source map, security reviews privilege/exfiltration, developer reviews parser contract, then an independent collector implementation #4443 may start.

No real cluster distribution, host list or execution ability is marked confirmed in this record because no approved probe/evidence has been supplied.

## 5. Normalized committed evidence contract for #4443

The following is a **KAORI target schema**, not a claim about a literal kubeadm JSON response. A trusted adapter maps *version-specific* output to this contract and rejects unexpected fields/structures.

```yaml
collection_run:
  run_id: "<opaque correlation ID>"
  cluster_id: "<KAORI registered cluster UUID>"
  source_kind: "kubeadm_check_expiration | provider_api | host_certificate | kubernetes_csr"
  source_version: "<validated tool/version>"
  source_authority: "<approved execution identity reference, never a secret>"
  node_id: "<registered node identity, nullable only for provider-wide sources>"
  started_at: "<UTC timestamp>"
  collected_at: "<UTC timestamp, only after successful collection>"
  outcome: "collected | partial | unavailable | unsupported | permission_denied | failed"
  coverage_expected: "<count or unknown, not guessed>"
  coverage_observed: "<count of supported source targets>"
  raw_output_stored: false
certificate_record:
  identity: "<stable source-qualified certificate ID>"
  component: "apiserver | etcd-peer | kubelet-client | ca | ..."
  kind: "leaf | ca | csr_observation"
  not_before: "<UTC timestamp or null>"
  not_after: "<UTC timestamp or null>"
  issuer: "<public issuer name if safely proven>"
  issuer_kind: "kubeadm | provider | external_ca | unknown"
  externally_managed: "<true | false | unknown>"
  node_id: "<source node ID>"
  source_run_id: "<committed run correlation>"
  status: "reported | not_collected | unavailable | unsupported | externally_managed | unknown"
```

A redacted **illustrative adapter result**, not actual production evidence:

```json
{
  "cluster_id": "REDACTED-CLUSTER-ID",
  "node_id": "REDACTED-NODE-ID",
  "source_kind": "kubeadm_check_expiration",
  "outcome": "unsupported",
  "coverage_expected": "unknown",
  "coverage_observed": 0,
  "raw_output_stored": false,
  "certificate_records": []
}
```

Important: `unsupported` with zero records is not a successful inventory, and `csr_observation` is never labeled an installed certificate.

**State precedence:** explicit collection failure/unsupported → unknown coverage; partial evidence → partial scope; successfully reported but expired certificate → Expired; a currently unexpired certificate from an old/stale collection → Stale Evidence, **not** Healthy. Expiration classifications must respect exact timestamps and a separately approved policy; 90/60/30/7 days are **proposals**, not approved KAORI taxonomy.

**Normalization invariants:** unique key by cluster, source, node and source-qualified certificate identity; upsert is idempotent; commit a complete bounded batch atomically; separate collection state from individual certificate rows; retain previous successful evidence while marking it stale if a later run fails; preserve node/correlation/source provenance; enforce cluster-level RBAC on both list and detail; allow no private keys, base64 kubeconfigs, bearer tokens or unredacted stdout; do not reprint rejected source data in parser exceptions.

## 6. Acceptance gates and blockers

| Workstream | Ready when | Explicit blocker |
|---|---|---|
| #4442 source discovery | Owner-verified distribution + provider identity + approved read-only source per pilot cluster; security source review | **Current discovery evidence missing** |
| #4443 committed collection | Approved source and identity; schema validation; worker/runner authorization; migration; negative and retry tests; committed/read-only evidence | Cannot substitute a live page request or stale TLS Secret inventory |
| #4444 read-only workspace | Actual #4443 committed data; role/cluster-scoped pagination 5; coverage+unknown states; no live calls | Do not place a placeholder second catalog card or claim `2 Capabilities` |
| #4445 renewal feasibility | Source ownership, exact provider capability and execution-plane contract independently approved | **Deferred pending Ansible orchestration readiness and operator approval** |

No certificate renewal, CA rotation, CSR approval, static-Pod restart or host mutation is permitted by this document.

## 7. Next evidence needed

For one **non-production pilot** cluster: approved distribution/version confirmation, control-plane/etcd topology, owning team, source tool/version, permitted read-only execution identity, redacted field inventory and permission outcome, actual collection window and full/partial coverage assessment. Then update this matrix and #4442 before #4443 collector work begins.

**References / implementation:** #4441 parent, #4442 discovery, #4443 collector, #4444 UI, #4445 future renewal; #556 Ansible authority; #757 Governance domain-first; `app/models/cluster.py`; `app/kubernetes/governance/tls_certificates/collector.py`.
