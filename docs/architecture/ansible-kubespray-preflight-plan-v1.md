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
