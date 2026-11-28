# Ansible / Kubespray preflight & Plan — evidence-gated review contract (v1)

Authority: #556 → #4796 → #4799 → #4800. Downstream mutation: #4801; worker OS maintenance: #4802.

## Current implementation

The first implementation is a **read-only preflight readiness projection** inside Ansible Connection → Validation & Capabilities. It reads only committed IntegrationInstance and canonical JobExecution state. It does not run Ansible, probe hosts, generate an approved executable Plan, or authorize Kubernetes mutation.

**Dependency ownership (#4978):** `app/infrastructure_automation/kubernetes/committed_preflight.py` owns the single committed preflight projection used by Plan review, currentness, dispatch and the worker. The Ansible provider exposes the same implementation through its existing preflight interface. `source_policy.py` owns the reviewed immutable Git/version pins and the committed-source qualification decision; GitHub remains authoritative for Git objects and transport, while the Ansible service owns provider-facing source posture. Domain code does not import Integration provider modules. The existing architecture-debt envelopes are unchanged, and the source, freshness, query-cap and final two blocked gates are preserved.

Source repository OXY7O/kaori-operations PR #6 is still an unmerged, non-executable candidate stacked on read-only source PR #2. A source-checked Git SHA is not evidence of qualified remote execution. The current worker is only the opt-in localhost read-only pilot (#4799).

A qualifying future remote worker must commit a JobExecution with integration_type=configuration_automation; exact connection ID; job_type=infrastructure_automation; operation=automation_kubespray_host_preflight; result_type=automation_kubespray_host_preflight_v1; status=succeeded; completion within 15 minutes; and exact registered Git repository/revision plus verified worker and self-managed-existing-host scope. The browser cannot submit attestation flags.

## Ten independent gates

| Gate | Evidence required | Missing/unknown |
|---|---|---|
| Immutable Git Source | Reviewed commit/versions | Blocked |
| Self-managed Target Scope | Authorized non-production existing Linux hosts | Blocked |
| Source & EE | Trusted pinned image/source provenance | Blocked |
| Host & Privilege | SSH host keys, credential reference, privilege admission | Blocked |
| OS & Capacity | Observed distro/kernel, CPU/RAM/disk and package manager | Blocked |
| CIDR & Network | Pod/Service/host network overlap and required ports | Blocked |
| DNS & Clock | Resolved DNS and synchronized time | Blocked |
| Topology & CRI/CNI | Control-plane/etcd quorum, endpoint and CNI/CRI | Blocked |
| Worker & Inventory | Admitted queue/exact immutable inventory | Blocked |
| Plan & Approval | Immutable plan fingerprint, maker/checker and active change window | Blocked |

Only the first **eight non-mutating evidence gates** may be satisfied by a fresh, trusted, source-bound worker observation; at that point the state is **Ready for Review**, never Ready to Execute. Worker-provided fields such as `worker_execution_admitted` or `maker_checker_approval_verified` are **ignored** for the final two gates. KAORI execution/credential authority, an immutable Plan, independent maker/checker decision and a current change window must be verified from their own committed records. An embedded declaration of attestation inside JobExecution is not a substitute for a signed execution envelope. Until those owners are implemented, the last two gates deliberately remain Blocked.

## Delivery sequence

1. #4799: qualified host identity, trusted SSH transport and read-only remote facts.
2. #4800: evidence-backed preflight/Plan, stale evidence rejection, immutable intent fingerprint and no mutation.
3. #4801: independent maker/checker approval + maintenance window, dedicated worker + pinned EE/source, exact target lock, native Kubespray execution, independent Kubernetes API verification and canonical Cluster evidence.
4. #4802: worker OS patch (separate cordon/drain/reboot/readback admission).
5. Subsequent scoped workstreams: cluster scaling, version/component upgrades and controlled backup/recovery.

No Flask-request SSH, arbitrary playbooks, raw secrets in broker/jobs, optimistic success from Runner rc, unmanaged Kubernetes source mutation, or production execution under this issue.

## Required real-host UAT before provisioning

Explicit disposable non-production hosts, source PR admission, target authorization, host-key trust, credential reference, signed EE provenance, cluster network/topology compatibility, privileged operation policy, independent human approval and change window, automation worker, and observed Kubernetes API postconditions.

## Focused Dev Container checks (NOT RUN in GitHub connector session)

- Ruff check and format on changed Python paths.
- djlint check on changed Jinja templates.
- pytest focused on test_ansible_kubespray_preflight.py and existing Ansible rendered detail/source-posture contracts.
- Existing verify_ui_reuse.py and verify_ui_style.py.
- Browser Visual QA: 10 gates, blocked default, light/dark/responsive, keyboard reading order, no remote reads or mutation controls.

Official Developer Check, Full Admission, host UAT and Human Acceptance remain separate; no staging/main promotion without those gates.

## Review evidence versus execution governance presentation (#5153)

The existing ten Kubespray gates have two independent meanings. The first **eight** qualify committed read-only source and trusted host evidence, while the final **two** belong to independent execution-worker/inventory admission and maker/checker approval plus maintenance window. The Ansible Validation & Capabilities workspace displays `Review Evidence N/8` and `Execution Governance 0/2` separately, preserves the original ten-gate status, and identifies the first missing requirement from the exact canonical gate sequence. Gate reasons are source-controlled, not copied from operator form data or generated using live SSH/Kubernetes reads. A `Ready for Review` eight-gate posture still means infrastructure mutation is blocked.

The existing shared `info_tip` Guide clarifies that a current review-only Plan is a canonical JobExecution artifact, not an executable plan, approval token, or assertion of Kubernetes API health. Source-only, stale, failed and newer in-flight host preflight retain the blocked state with a next review prerequisite; even simulated valid worker evidence always retains execution governance blocked. The action guard, default pagination 5, four-tab navigation, all provider trust boundaries and downstream #4801 authority remain unchanged. Check Ruff/djlint/pytest and browser light/dark/mobile semantics on the exact candidate before admission.

## Additional execution-compatibility authority (#5156)

Before offering a review-only Plan, the Ansible Validation workspace also evaluates the source-defined `kubernetes_lifecycle` execution compatibility matrix independently of the annual KAORI five-year Kubernetes API support policy. The exact candidate Kubespray source/version/Ansible toolchain/OS remain governed by the approved source and static preflight. Only currently supported, exact-version, source-checked, EE digest-referenced and preflight-qualified evidence can show **Review Only**. Provision, Verify, Scale, Upgrade, Node Maintenance and Recovery remain blocked until their own operation and non-production mutation authority exists. The matrix does not turn a `current` Kubernetes API version, source registration or a worker assertion into permission to Run.

## Committed host-registry freshness guard (#5163)

The canonical committed preflight reader additionally requires a worker-owned `host_registry_fingerprint` equal to the current scoped KAORI host-registry intent and an exact match of all three observed asset IDs, roles, addresses and SSH ports. It reads at most four active assignments (three pilot members plus one overflow sentinel) and never falls back to an older attempt. Missing binding, changed identity, role, endpoint or membership blocks review, including dispatch, worker materialization and Plan currentness consumers of the committed reader. Only a digest is required in the attested binding; no new persistence or approval authority is introduced. This is a registry-freshness increment, not credential-version/SSH-trust admission, immutable Plan schema completion or remote worker attestation production. The remote producer remains separately gated under #5162/#4799/#5066, and both execution-governance gates remain blocked.

## Exact dispatch and committed access evidence fence (#5163)

The committed preflight reader requalifies all three exact current host memberships and their existing reference-only `AutomationHostAccessBinding` records, including current observed Vault representation/version and host revision. It hashes only canonical member references and collection commit generation into an opaque, order-independent `host_access_fingerprint`. This must equal the separately trusted worker's attested aggregate; an absent, stale, rotated or mismatched reference blocks review. The registry fingerprint and execution-environment identity must also match. Metadata correlation never proves credential-use policy or SSH trust: the independent worker producer, typed credential authority and target authorization remain gated by #5162/#4799/#5066. A newer wrong-queue or malformed attempt cannot resurrect older evidence.

Plan summary and fingerprint include the registry and host-access digests. Dispatch freezes the same fields in the canonical JobExecution parameter fingerprint. The worker must match its own task/job/connection envelope and the exact queued parameter fingerprint before materializing and after its final evidence checkpoint. Currentness likewise compares the original dispatch fingerprint and rebuilt summary; earlier artifacts missing the new mandatory fields fail closed. This remains DB-only review material, not an approved Run, and neither dispatch nor worker invokes a provider. Existing 8+2 preflight and Violet review UI are retained. PostgreSQL concurrency, remote worker producer, independent credential-use authorization, maker/checker/window and actual provisioning remain separate acceptance requirements.

### Persisted integration and freshness

The #5180 SQLite fixture is reused to record the actual three governed metadata bindings and audit events. Repeated readback must produce the same order-independent digest; changes to host revision, pinned version, destroyed version, missing binding or disabled source block, and a new collection generation changes the digest. ORM reads refresh previously loaded records, and the worker refreshes its request and source records after the canonical progress checkpoint. This is readback freshness, not a transaction-wide execution lock or proof of remote SSH; the independent execution boundary still must take a bounded target lock and revalidate. PostgreSQL concurrency/UAT remain separate.

The currentness projection retains the existing eight-plus-two gate presentation and identifies inventory/access drift or source/EE drift as a sanitized blocker, rather than misrepresenting it as a successful preflight or exposing Secret metadata. Plan target projection and the repeated dispatch qualification use named, shared validation boundaries within the existing Code Health limits; no debt allowance is changed.


### Governed Plan acknowledgement candidate (#4800/#4801)

The local review-lane acknowledgement service follows the existing canonical
AuditEvent approval pattern used by Kubernetes Tenant release handoff. It
does not duplicate the immutable Plan JobExecution or create a separate
permission system. It requires an explicitly enabled local security review
transaction, exact current latest Plan, actual canonical connection and
three registered hosts, and distinct Plan requester/checker with current
explicit integrations.manage, inventory.view and jobs.execute permissions.
This permission combination is a proposal for review, not mutation authority.

The acknowledgement pins the Plan job ID, Plan fingerprint, source/EE,
inventory/registry/access digests, maker/checker, bounded UTC maintenance
window (candidate maximum two hours), opaque change reference and expiry
(the earlier of Plan expiry and window end). The window must begin before
the Plan expires; execution admission remains blocked. The writer takes the
existing canonical transaction-scoped job resource locks for the exact
connection and all three host identities and refreshes the locked records
before appending mandatory AuditEvent. It rejects duplicate acknowledgement,
a live overlapping acknowledgement for the connection and same-Plan
reactivation after revocation. Latest acknowledgement readback requalifies
the Plan, actors, active window and exact record. Revocation appends an audit
event without requiring stale source/preflight to become healthy again.

No public writer, mutation job, long-lived Run lease or Kubernetes execution
is introduced. A separate independently admitted runtime must establish
cross-connection conflicting Run prevention for the entire worker lifetime,
fresh signed source/EE, operation-specific credentials, native preflight and
actual target mutation authorization. The last two preflight governance gates
remain blocked; do not mark either ready from this candidate acknowledgement.
Native PostgreSQL concurrency, independent Access review and UAT remain open.


### Independent pilot Kubernetes API readback candidate (#4801)

The independent native readback adapter accepts an internally selected
canonical KubernetesConnection with strict TLS, exact registered HTTPS
server, a separately established kube-system namespace UID and expected
three node identities derived from immutable Plan/inventory. Runner success
or a Runner-supplied kubeconfig/identity is not sufficient. It reuses the
existing container-orchestrator Integration Kernel client, makes bounded
GET-only observations of version, API /readyz and /readyz/etcd, the exact
unpaginated three-node set (names, internal IPv4, role, unique native UID,
Ready/no pressure/no cordon), fixed control-plane mirror pods and fully
available CoreDNS deployment. It rechecks namespace identity, nodes and
API/etcd endpoint health before returning only sanitized correlation
fingerprints and observation time. No raw endpoint, node addresses or
provider credentials are returned in the committed summary.

The expected namespace UID must come from independent target/cluster
authority, not from the same observation or Runner result. The fixed
component names and CoreDNS deployment are candidate postconditions to
qualify against the actual admitted Kubespray source. API etcd readiness
is not direct etcd quorum/backup/restore evidence; CNI/CRI and full
provisioning remain unverified. The adapter does not register a Cluster,
persist NodeInventory, create IntegrationBinding, dispatch a verification
job, mutate infrastructure or mark a Run successful. These downstream
steps require admitted Run provenance, separately authorized readback,
canonical cluster registration/inventory synchronization and binding,
and controlled native UAT. Synthetic SDK regressions are not native UAT.


### Durable pilot target exclusion (#4801)

The local review reservation service extends the existing Plan acknowledgement
with a database-enforced persistent exclusion. One immutable Plan JobExecution
owns seven unique active resource claims: one connection, three canonical
host IDs, and three SHA-256 endpoint-address references. Endpoint exclusions
are deliberately global and conservative across environments; overlapping
RFC1918 address spaces require a future independently qualified network
identity model, not silent bypass. All claims and the reservation AuditEvent
commit in a single PostgreSQL transaction under canonical resource locks.
A conflicting active claim or prior reservation of the same Plan denies
the entire request. The reservation persists across transaction exit,
worker restart and Plan expiry.

The internal review-only maker release requires exact reservation identity,
all seven active claims, current explicit permissions, original maker and no
child JobExecution of the Plan. It retains released records and appends
mandatory audit. No timer, retry, cancellation or generic stale-job
recovery removes claims. The migration starts empty and refuses downgrade
when reservation history exists. The canonical JobExecution retention domain excludes Plans referenced by
any target claim, including released history, from archive selection and
rechecks the exclusion under ordered JobExecution row locks before cleanup.
If a claim appears after archive selection, cleanup preserves the Plan and
the existing partial-cleanup reporting remains authoritative. The restrictive
Plan FK stays as a final database safeguard; no claim is removed by retention.
The review-lane regression uses synthetic SQLite data; native PostgreSQL
concurrency and migration validation remain pending.

This service does not establish Run admission, freeze every provider or connection change,
start a worker or approve a mutation. Future admitted worker integration
must revalidate inventory/source/access, atomically associate the exact
claims with a one-attempt canonical Run, guard every competing infrastructure
operation, and replace the review-release path with independently verified
terminal/recovery reconciliation. Normal host registry/enrollment/assignment/edit/retirement writers now
use the same resource keys and reject active claims before persistence.
Connection management, credential/issuer revocation and future execution
admission retain their own authorities; connection management is not yet
integrated with the reservation guard.
The new reservation is not an execution lease or a third approval channel.
No default opt-in or route is added. Synthetic schema/uniqueness tests
are not PostgreSQL concurrency or native host acceptance.
