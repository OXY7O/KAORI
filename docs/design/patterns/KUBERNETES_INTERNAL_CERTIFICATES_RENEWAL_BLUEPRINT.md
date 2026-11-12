# Kubernetes Internal Certificates — Governed Renewal Blueprint

> **Design-only / deferred** — 2026-11-12 operator decision. Authority #4441 / #4445, source discovery #4442, read-only evidence #4443, operational UI #4444, Ansible execution authority #556. **This document does not authorize execution.** No renewal/rotate button, schedule, host privilege, Ansible job or CA operation is enabled by this design.

## 1. Recorded product decision

KAORI builds **Internal Certificates monitoring first** (source-qualified, committed evidence and an RBAC-scoped read-only workspace). Lifecycle mutation becomes a separate, separately approved feature **after an Ansible orchestration integration is operational, audited and admitted**.

**KAORI normalizes, correlates, governs and audits. kubeadm / provider / external CA owns certificate lifecycle; approved Ansible executes applicable host changes; Git defines execution automation; committed evidence proves the result.**

- KAORI must **never** become a CA, signer, direct SSH console or clone of kubeadm.
- A certificate can be valid but **unsupported for KAORI rotation**. UI must show the distinct authoritative state and owner handoff.
- One cluster's kubeadm procedures cannot be assumed safe for another cluster. No universal `Rotate All` button.
- Kubelet client rotation is normally automatic where configured; show monitor/diagnose rather than force renewal. Kubelet serving CSRs must not be automatically approved without identity verification. kubeadm does not provide automatic CA rotation.
- TLS Secrets/Ingress certificates remain in the existing TLS Certificates capability, not this internal PKI surface.
- No private keys, CA keys, kubeconfig credentials, CSR keys, raw privileged stdout or secret path values may be ingested into KAORI committed evidence or Activity Audit.

## 2. Boundary architecture

```text
Kubernetes → Governance → Internal Certificates
  │
  ├─ Read-only committed view (#4443 + #4444)
  │     Source & trust → Identity/CA family → Expiration/Posture → Provenance
  │     Coverage, freshness and owner / provider-specific handoff
  │
  └─ Future (disabled until separately admitted)
        Renewal Plan Request → Policy/Capability decision → Human Approval
        → Preflight evidence + reservation/lock + exact scope
        → KAORI Orchestration Adapter
        → Approved Ansible job / native provider controller
        → kubeadm/managed-provider/PKI authority
        → Post-change evidence, health checks, auditable outcome
```

External engines remain authoritative for command/version compatibility and execution state. KAORI persists normalized orchestration IDs, policy decisions and committed evidence. Regular UI reads committed KAORI state, not a synchronous live provider call.

## 3. Support matrix and future UI behavior

| Source ownership | Monitoring | Potential operation | UI action after admission |
|---|---|---|---|
| kubeadm-managed control-plane leaf certificates | Qualified node-local evidence | Target-specific `kubeadm certs renew <name>` through approved Ansible and per-node lifecycle | **Request Renewal**, only if support + preflight gates all pass |
| kubeadm etcd peer/server/client | Qualified per-host evidence + etcd topology | Separately approved etcd-specific HA procedure and verification | **Request Renewal** with high-risk controls only; otherwise external handoff |
| Kubernetes / etcd / front-proxy CA | Public CA expiry/status | Manual multi-step CA trust rotation; kubeadm does not automate it | **View Owner Runbook**, not auto renew |
| kubelet client | Installed certificate evidence; CSR state separately | Usually kubelet-native auto-renewal; handle failure through incident runbook | **Rotation Monitoring**, no forced default renewal |
| kubelet serving | Installed cert + CSR signer/approval state | Verified signer/identity and change-controlled approval where approved | **Review CSR / Owner Handoff**, never blanket auto approve |
| Managed Kubernetes control plane | Provider API only if exposed | Provider-controlled | **Open Provider Procedure** or **Provider Managed** |
| External CA/custom PKI | External verified records | CA system of record | **External Handoff** or **Unsupported** |
| Unknown distribution or incomplete evidence | `Not Collected` / `Unsupported` / `Stale` | **None** | **No mutation action** |

*The table is a decision framework, not proof that any registered cluster currently supports these operations.* Exact tooling and paths are not automatically authorized.

## 4. Committed contracts (future implementation, not current DB migration)

### 4.1 Source qualification

Each supported cluster/node/component source shall record:
```text
cluster_id, node_id, certificate_identity, certificate_kind, source_kind,
source_version, managed_by, issuer_kind, evidence_collected_at,
not_before, not_after, source_freshness, coverage_status, collection_run_id,
owner_id, capability_assessment, assessment_version, external_handoff_ref
```

No UI action may be offered without a **fresh, successful** source-qualified record and an independently approved capability assessment. `Unknown` or an empty recordset cannot become `Healthy`.

### 4.2 Renewal capability decision

Store a **separate** per cluster × component × owner decision (not a boolean `can_renew`):

```text
capability_state:
  monitor_only | supported_via_approved_engine | provider_managed |
  external_handoff | unsupported | unknown
reason_code, authority, approved_runbook_ref, automation_git_revision,
executor_binding_ref, required_approval_policy, risk_class,
assessment_version, assessed_at, expires_at, security_review_ref
```

This is future schema design, pending existing taxonomy/RBAC review; it is not an instruction to create database tables or new enum names immediately.

### 4.3 Governed renewal request / evidence

```text
request_id, idempotency_key, exact cluster/node/certificate scope,
requester, impact/risk tier, maintenance_window, preflight_evidence_refs,
change_ticket_ref, approval_actor_and_time, policy_decision,
approved_automation_ref_and_git_sha, executor_job_id,
provider_operation_id, started_at, completed_at,
before_not_after, after_not_after, leaf_or_ca_kind,
health_before_ref, health_after_ref, post_validation_ref,
rollback_or_recovery_ref, final_outcome, audit_correlation_id
```

Record references/IDs, **not** credential material or unredacted host command output. Use KAORI job + Activity Audit/evidence patterns and existing rollback/recovery conventions; do not create a separate execution subsystem.

## 5. Future workflow state machine

```text
Discovered (committed, qualified)
  → Not Eligible / Monitor Only
  OR → Plan Draft
        → Preflight Pending
        → Preflight Passed / Blocked
        → Approval Pending
        → Approved / Rejected / Expired
        → Scheduled (approved maintenance window)
        → Locked (exclusive cluster/node/PKI identity)
        → Executing (approved external job)
        → Post-Validation
        → Verified & Evidence Committed
          OR Failed / Recovery Required
```

`Verified` requires new committed certificate expiry **and** independent API/etcd/cluster health evidence. A successful Ansible exit code is not an acceptance criterion on its own.

- Preflight evidence and approval must have **bounded freshness** and be invalidated when target, requested certificate, CA/owner, source state, playbook revision, maintenance window or execution identity changes.
- Make requests idempotent; no duplicate renewal for same exact target/window. One active operation per compatible PKI authority/cluster scope. Network retries must reconcile the execution ID, not start a second run.
- Cancellation after mutation begins is **not** an automatic rollback. A failed etcd/control-plane renewal enters a controlled recovery state.

## 6. Required mutation preflight (not yet implemented)

**Universal gates:** identified distribution and PKI owner; certificate vs CA classification; exact node/cluster identity; active, fresh committed evidence; user RBAC + step-up if required; approved automation Git commit; secret-safe approved engine binding; change ticket; maintenance window; owner approval; service-impact evaluation; recoverable backups of control-plane/etcd state and trust material in their **approved protected location**, never KAORI database; verified recovery owner.

**Control-plane gates:** HA membership and number of available apiservers; API readiness, scheduler/controller health and service endpoints; existing client connections; load-balancer/endpoint strategy; independent node/clock validity. A multi-control-plane cluster uses **one-node-at-a-time** approved operations, with health/expiry verification between nodes; never parallel renew all nodes.

**etcd gates:** peer membership, quorum, leader/current health, snapshot/restore rehearsability and external-etcd topology. A failed quorum gate is BLOCKED, not overridden by a low expiry value.

**Rotation-specific gates:** detect kubeadm-managed vs external CA and correctly scope the leaf certificate. CA rotation must use a separately approved manual trust-distribution plan; changing CA key material or forcing CSR approvals is out of scope.

**Execution identity:** use approved Ansible inventory/credential references and host permissions; no raw SSH from a web handler; allowlist exact command/targets and bounded output. Job parameters cannot become arbitrary shell commands, paths or YAML injection.

## 7. Execution and recovery design

- Plan is Git-defined and pinned to immutable commit SHA; execute via existing Ansible orchestration provider once admitted. Use native check/validation and module/task idempotence where possible; never treat check mode as a guarantee that certificate mutation is safe.
- For supported kubeadm leaf rotation, execute **certificate-specific** renewal under exact approved host/runbook. The mechanism may require controlled restart of static control-plane Pods or component reload and re-distribution of renewed kubeconfig certificates. This is a deployment-sensitive change and always needs human acceptance.
- Before any mutation, the owning operations team stores and verifies an encrypted/controlled recovery copy and relevant etcd snapshot as appropriate. KAORI stores only backup reference + verification result.
- After mutation, collect new host-local validity from the same authoritative source, test API readiness/health and etcd quorum, compare identity and validity, verify dependent components and commit source-qualified evidence.
- On post-check failure: pause remaining hosts, block further automation, escalate incident, preserve execution/recovery evidence and invoke approved recovery **manually**. Do not assume copying old certificates back is always safe after CA trust changes.
- CA rotation and managed-provider lifecycle transitions remain **external-handoff workflows** until independently approved.

Kubernetes reference: [kubeadm renewal](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/), [certificate rotation](https://kubernetes.io/docs/tasks/tls/certificate-rotation/), [manual CA rotation](https://kubernetes.io/docs/tasks/tls/manual-rotation-of-ca-certificates/).

## 8. UX reserved for future (not live)

Current read-only workspace (#4444) will show:
- Source Readiness, Collection Freshness, Coverage, Expiry Posture, Owner/Authority, Certificate Inventory (default 5/page), Not Collected/Unsupported/Unknown/Expired as distinct statuses, and evidence-driven details.
- **Rotation Readiness** as an informative, **non-actionable** assessment: Unsupported / Provider Managed / External Handoff / Pending Assessment / Candidate for Future Governance. Avoid future feature buttons that suggest executable capability.

Only after separate implementation/admission may there be a **Request Renewal** action. Its workflow must have distinct Plan/Preflight/Approval/Execute/Verify/Evidence steps, explicit risk, and a clearly visible provider/executor authority. No hidden click-to-rotate within a read-only registry.

## 9. Security risks and non-negotiable negative tests

| Risk | Gate / test |
|---|---|
| Private/CA key or kubeconfig exfiltration | Refuse ingest; scrub standard outputs; no raw executor stdout in DB/UI/logs; scan artifacts |
| Cross-cluster RBAC leakage | Enumerate/filter only authorized clusters; negative tests for direct URL/API with wrong cluster |
| Unsupported managed provider invoked as kubeadm | Matrix + capability gating; provider unsupported returns no action |
| External CA falsely marked renewable | Source/issuer ownership validation; no kubeadm mutation |
| Incomplete/old evidence marked healthy | Coverage/freshness failure states precede expiry |
| Concurrent HA/etcd renewal | Exclusive locks, one-by-one host sequence, quorum checks; negative tests |
| Unauthorized schedule or expired approval | Role/step-up, immutable scoped approval and maintenance window |
| Untrusted Git playbook or injection | Pinned Git SHA, signed/approved template, validated parameters and engine identity |
| Ansible/transport failure mid-rotation | Correlate existing job, never blindly retry; manual recovery workflow |
| CSR spoofing and blanket approval | Disallow default automated CSR approvals; verify signer and node ownership |

## 10. Future quality gates / full acceptance

**Engineering:** existing `ruff`, `pyright`, `pytest`, `djlint`, `prettier`, contract and `verify_*` gates appropriate to touched code; Developer Check, Full Admission, Visual QA, DAST/security checks. Do not write a redundant verification framework.

**Staging/UAT:** controlled disposable kubeadm pilot with (a) single control plane and (b) multi-control-plane HA if relevant; expired/near-expiry, partial coverage, stale evidence, revoked permissions, externally managed CA, provider-managed, kubelet CSR, etcd quorum failure, transport/runner interruption, node fail/rejoin, backup recovery simulation. Exact pre/post expiry, API and etcd health, audit and rollback runbook evidence; security approval and explicit Human Acceptance.

**Release:** separate implementation child issue and PR; stage through `kaori/review/staging-uat` → official admission → `kaori/staging` UAT → human acceptance → `main` promotion, release/tag if required. Deployment and infrastructure mutation remain blocked until security and operations approval.

## Read-model extension (operator-attested evidence)

The interim #4461 metadata-only import provides source-qualified committed
certificate records prior to Ansible execution integration. Operator attestation
is not an eligible renewal capability decision. Its `InternalPKICertificateInventory`
values are **not proof** of installed/running certificates; future #4445
preflight must revalidate the authoritative source through the approved
Ansible/provider engine and compare control-plane/etcd health. A valid
operator-supplied expiry must never enable a Renew action automatically.
See [Evidence Import Runbook](KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md).

## 11. Deferred dependency and restart checklist

**Hold point:** no suitable admitted Ansible orchestration execution binding + approved Git playbook and credential references for this Kubernetes PKI scope have been evidenced. #4445 is therefore **design/feasibility only**. Do not schedule background renewal, create buttons, grant sudo or rotate certificates while held.

When the operator says “resume internal certificate renewal”, start from these existing workstreams rather than rediscovery:

1. Confirm #4442 source support and owner decision, and #4443/#4444 committed read-only evidence and UI acceptance. Check current merged code/docs.
2. Verify #556 Ansible provider integration, job execution/readiness and approval hooks have been admitted for the **actual** cluster topology, without cloning execution code.
3. For each exact certificate/source family, review decision matrix, privileges, backup/restoration, incident escalation and multi-node impact; obtain security/ops sign-off.
4. Break down #4445 into implementation child issue(s): capability assessment/eligible policy; approved Ansible template + immutable version; preflight/approval; dispatch/state correlation; post-validation/recovery/evidence; limited first pilot. No umbrella large PR.
5. Execute canary non-production UAT and separately authorize production pilot only after manual acceptance.

**Open work is not considered complete simply because this blueprint was merged.** Design review, approved source evidence and future Ansible readiness are required.

## References and record

- #4441 Internal Certificates foundation
- #4442 per-cluster source/authority matrix; [source contract](KUBERNETES_INTERNAL_CERTIFICATES_SOURCE_CONTRACT.md)
- #4443 committed PKI evidence collector
- #4444 implemented-only read-only workspace and second Governance capability card
- #4445 renewal feasibility / deferred design authority
- #556 Ansible infrastructure automation architecture; #757 Governance implemented-only authority
- `app/models/cluster.py`, `app/kubernetes/governance/tls_certificates/collector.py`
