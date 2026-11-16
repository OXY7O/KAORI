# Ansible / Kubespray preflight & Plan — evidence-gated review contract (v1)

Authority: #556 → #4796 → #4799 → #4800. Downstream mutation: #4801; worker OS maintenance: #4802.

## Current implementation

The first implementation is a **read-only preflight readiness projection** inside Ansible Connection → Validation & Capabilities. It reads only committed IntegrationInstance and canonical JobExecution state. It does not run Ansible, probe hosts, generate an approved executable Plan, or authorize Kubernetes mutation.

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
