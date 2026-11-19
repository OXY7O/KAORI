# Kubernetes Internal Certificates — Source and Support Contract

> **Status:** Operator-observed non-production kubeadm v1.36.4 source format documented, 2026-11-12. A read-only Governance workspace (#4453) and manual metadata import (#4461) exist; a 14-record pilot batch was committed and audit-verified in the operator's Dev Container on 2026-11-12. Production automated ingestion remains separate. Production source qualification and automated collection (#4443) remain pending. Renewal/CA rotation stay native to the platform or PKI owner **outside KAORI** by decision #4445; Ansible is collection-only. Authority: #4441 / #4442.

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

### Observed local pilot — Docker Desktop (2026-11-12)

The operator confirmed the active `kubectl` context is `docker-desktop`,
two nodes `desktop-control-plane` and `desktop-worker` are Ready with
Kubernetes `v1.36.4`, and `kindnet` pods exist. **This supports a
kind-style Docker Desktop provisioner** but is not proof of cluster
PKI authority. Subsequent owner-supplied direct read-only observation
**inside the Docker Desktop control-plane container** established that
`kubeadm version -o short` reports `v1.36.4` and
`kubeadm certs check-expiration -o json` returns
`CertificateExpirationInfo / output.kubeadm.k8s.io/v1alpha3`, with
**11 leaf/kubeconfig records and 3 CAs**.

| Docker Desktop source / capability | Evidence decision | Lifecycle boundary |
|---|---|---|
| kind-style Docker Desktop provisioner | The **provisioner** is managed by Docker Desktop/kind; not an automatic host PKI source or renewal engine | Docker Desktop remains lifecycle owner |
| `kubeadm v1.36.4` on `desktop-control-plane` with exact `output.kubeadm.k8s.io/v1alpha3` JSON | **Pilot source verified for metadata only**, now supported by the deliberately version-qualified operator-only `flask prepare-internal-pki` adapter and existing strict v1 import after human review | Source-reported `NotAfter` is not proof of active use; no rotation |
| Generic kind output, unknown other kubeadm versions, inaccessible control plane or alternate CA | **Unsupported / Not Verified** until a separately reviewed adapter and source identity exist | No mutation action |

**Permission boundary:** the operator obtained this read-only source from a
local non-production Docker Desktop node they administer. KAORI never
runs `docker exec`, privileged SSH, file mounts or host commands in an
HTTP request. Never extract any private key, PEM, CSR, kubeconfig or
CA signing material. The new adapter accepts **only exact known public
metadata fields** and does not change the existing source importer,
RBAC, migration or cluster executor. Raw report and prepared manifest
remain operator-local outside Git.

**Observed validity from this report:** ten of the leaf/kubeconfig entries
have `NotAfter=2027-09-11T04:08:18Z`, apiserver has
`NotAfter=2027-11-12T03:45:43Z`, and three CAs have
`NotAfter=2036-09-08T04:08:18Z`. The operator subsequently committed the reviewed 14-record metadata batch `107855b3-8f8b-407a-84fe-9bdf7e75be38` on 2026-11-12, and verified 11 leaf + 3 CA inventory records and Activity Audit in Dev Container. This is **operator-attested UAT evidence**, not automatic collection, verified installed certificates or full cluster coverage.

Implementation and safe operator steps:
[KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md](KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md).
Ansible is planned solely for approved **read-only collection** (#4443). Renewal and CA rotation remain native platform/PKI-owner procedures outside KAORI (#4445).

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

**Automated ingestion qualification:** today's `import_attested_pki_metadata` CLI/read model is specifically **operator-attested**. A future Ansible/provider collector under #4443 must not silently reuse that provenance label: it must record actual authorized job/source identity, source kind/version, per-node coverage, run outcome/freshness and distinguish automated source-qualified evidence from manual operator attestation in the committed read model. Reuse strict metadata normalization but extend the execution evidence contract separately with compatibility/negative tests. Provider-owned renewal remains outside this collector.

## 6. Acceptance gates and blockers

| Workstream | Ready when | Explicit blocker |
|---|---|---|
| #4442 source discovery | Non-production Docker Desktop v1.36.4 output schema observed; owner validates source identity, security and local-only access | **Pilot report now supplied; source/owner review still required for admission and other clusters** |
| #4443 committed collection | Existing strict operator-only import and schema/read model are implemented; automated worker/runner requires separate authority | **Automated PKI collection remains deferred; CLI preparation does not perform a provider call** |
| #4444 read-only workspace | Existing visible Source Pending card and registry, permission-aware, committed read model; verify actual 14-row pilot import, scoped 5/page, coverage/unknown, no live calls | **Empty until operator-approved source import; UAT/Human Acceptance outstanding** |
| #4445 native renewal ownership | Platform/PKI owner and native procedure documented | **No KAORI renewal implementation; Ansible limited to approved read-only collection** |

No certificate renewal, CA rotation, CSR approval, static-Pod restart or host mutation is permitted by this document.

## Operator-attested PKI inventory milestone (#4461)

While automated host-side collection #4443 remains blocked by approved read-only
execution identity, a **strict metadata-only import** is available for an
authorized kubeadm pilot under #4461. The operational source mapping,
normalization contract, SQL migration, audit and Dev Container command are
documented in
[KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md](KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md).
The collected PKI certificate records are **operator-attested**, never
provider-verified installation state. No raw CLI output, PEM, keys, kubeconfigs,
or provider secrets may be stored or committed to source control.

The Internal Certificates workspace may show these actual committed
certificates after an approved source manifest is imported and the database
migration is applied. Until then, the certificate table is empty or
**Inventory Schema Upgrade Required**; the Source Registry continues to report
committed cluster registration metadata. The planned Ansible collector is **read-only**; KAORI renewal execution is not an implementation target. No sample manifest counts as
live PKI evidence.

## Native platform renewal ownership (approved monitor-only boundary)

The historical KAORI-renewal workflow is superseded. The retained [native renewal ownership decision](KUBERNETES_INTERNAL_CERTIFICATES_RENEWAL_BLUEPRINT.md) (#4445) confirms KAORI collects and reports evidence only; kubeadm, managed providers and external PKI owners perform renewal outside KAORI. No Renew button or Ansible renewal job is planned.

## 2026-11-12 UI delivery amendment — implemented source-readiness stage (#4453)

The operator explicitly requested a **visible and usable** Internal Certificates workspace before control-plane PKI collection is available. Issue #4453 authorizes a narrow first-stage exception to the earlier “no card before #4443” instruction: show **Internal Certificates — Source Pending** beside TLS Certificates, with a real read-only route and the existing committed cluster registry as its source. This is **not** a certificate inventory, PKI readiness verification, or collection success.

The first-stage page reads only registered `Cluster` and associated `KubernetesConnection` metadata. It shows the connection-detected platform/version as a **non-authoritative hint**, never as proof of a kubeadm installation or supported PKI execution identity. For each registered cluster, the internal PKI states remain **Not Collected**, **Not Verified**, and **Unknown** until a qualified #4443 collector commits actual PKI certificate records. All normal requests avoid provider/API calls; no fabricated `not_after` date, empty Healthy count, CA material, or renewal action appears.

The route has separate `internal_certificates.view` plus `governance.view` and `clusters.view` guards. Existing KAORI RBAC role scope is global, **not per-cluster**; finer source-specific access must be defined and tested before a future PKI certificate detail implementation. Default roles receive the new read-only permission after governed `flask seed-rbac`, not as a read-path side effect.

**Milestone distinction:** #4453 closes only after exact-SHA QA and Human Acceptance of the **source-readiness** page. #4443 remains blocked on verified PKI source/identity; full #4444 committed certificate inventory/expiry posture remains OPEN and must not be marked complete from this UI-only phase. #4445 assigns renewal to native platform/PKI owners; Ansible is planned for read-only collection only.

## 7. Next evidence needed

For one **non-production pilot** cluster: approved distribution/version confirmation, control-plane/etcd topology, owning team, source tool/version, permitted read-only execution identity, redacted field inventory and permission outcome, actual collection window and full/partial coverage assessment. Then update this matrix and #4442 before #4443 collector work begins.

**References / implementation:** #4441 parent, #4442 discovery, #4443 collector, #4444 UI, #4445 native renewal ownership; #556 Ansible collection authority; #757 Governance domain-first; `app/models/cluster.py`; `app/kubernetes/governance/tls_certificates/collector.py`.
