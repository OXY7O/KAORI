# Ansible execution and self-managed Kubernetes lifecycle — first pilot contract

> **Scope:** design/decision contract for #4796, building on approved Infrastructure Automation foundation #556 and proposed hybrid execution-boundary context #1907.  
> **Stage:** approved execution/repository direction; first localhost-only worker and read-only playbook are on bounded Draft PRs (`KAORI#4807`, `kaori-operations#2`) and are **not yet accepted real-provider UAT or infrastructure mutation authority**.  
> **Admission:** Dev Container pre-admission / Human UAT review; official admission **HOLD**.

## 1. Authority and ownership

Use the existing KAORI Integration Kernel, canonical JobExecution, Activity Audit, scoped RBAC, and Kubernetes managed asset/integration ownership. This contract extends — and must not silently widen — #556's initial existing-Linux-host MVP, which explicitly excluded Kubernetes automation and VM provisioning.

**Ansible executes; KAORI orchestrates; Git defines; Evidence proves.**

| Responsibility | Authority |
|---|---|
| Cluster topology intent, risk/approval/maintenance policy, immutable run provenance, normalized execution/audit evidence | KAORI |
| Playbooks, roles, collections, Ansible facts, execution semantics, error/events, check/diff | Ansible and selected upstream automation |
| Self-managed Kubernetes bootstrap and supported in-place lifecycle implementation | A separately qualified, revision-pinned Kubespray adapter; cluster operator retains ownership |
| Kubernetes node/workload/etcd health, Kubernetes version, and authoritative postconditions | Kubernetes API and cluster-native mechanisms |
| Linux host allocation/creation, power and underlying compute lifecycle | External virtualization/compute provider, **outside first pilot** |
| Managed Kubernetes control-plane provisioning and upgrades | Its own cloud/provider lifecycle API and a separate future KAORI adapter |
| SSH, become and other secrets | Approved secret authority and short-lived worker reference; never Git inventory, KAORI ordinary persisted state, event logs or output |

The canonical Integration hierarchy is capability first, provider second, instance third. The planned Ansible connection is **Integrations → Orchestration → Ansible → execution instance**, while operator actions belong to the relevant **Infrastructure Automation** or **Kubernetes → Operations** product surface. The existing `Cluster` managed asset and `KubernetesConnection` (kubeconfig/API/TLS) keep their established ownership.

## 2. Initial supported target

- **In scope:** existing, approved Linux VMs or bare-metal machines reachable over an authorized SSH boundary; fresh non-production self-managed Kubernetes cluster; explicit per-cluster binding and verified post-install adoption into existing Kubernetes Integration.
- **Initial pilot:** one control-plane machine and two worker machines, strictly non-HA and disposable/non-production, solely for validating create → verify → controlled worker OS patch → reverify.
- **Not in scope:** creating VMs; Kubernetes managed services (EKS, AKS, GKE, OKE); generic kubeadm/CA certificate renewal; production unattended patch/upgrade; arbitrary Ansible console; playbook authoring UI; provider token/root-secret storage. See #4445 for currently approved monitor-only Internal Certificates.
- **Next separately approved scopes:** HA/control-plane maintenance, supported Kubernetes version upgrades, CNI/CSI and other add-on upgrades, node join/remove/replace, drift/compliance, recovery, managed-provider lifecycle adapters.

Do not equate OS security patching, kubelet/Kubernetes version upgrade and CNI/CSI upgrade: each must have independent preflight, execution, compatibility and verification contracts.

## 3. Execution topology

```text
KAORI Flask / HTMX (request + authorization)
        |
PostgreSQL: Plan / Approval / JobExecution / committed evidence
        |
Existing Redis/Celery infrastructure
        |
Dedicated, queue-isolated Automation Worker (not Flask process)
        |
ansible-runner (Python interface and event/artifact handling)
        |
Pinned and isolated Ansible Execution Environment
        |
Immutable selected Git revision and scoped execution inventory
        |
Approved SSH + become network boundary
        |
Existing Linux hosts → self-managed Kubernetes
        |
Independent native API/provider read-back → committed verification / Activity Audit
```

`ansible-runner` is a library/CLI; it is **not itself a VM or scheduling service**. **Accepted long-term default:** dedicated logical KAORI Celery automation worker/container with a separate queue and controlled pinned execution environment. An isolated worker VM is an optional deployment placement if network segmentation, volume, blast-radius or privilege isolation requires it; do not require one for the initial pilot.

Use existing canonical queue/worker registration, retry/lease, JobExecution and audit contracts; **do not create a second scheduler, generic shell endpoint, private job-state model or synchronous web-request mutation**. Exact queue identifier, resource limits, container runtime security and registered operations must be accepted in a bounded worker implementation issue, not inferred from this document.

Runner process exit code and native Ansible `successful` are **execution outcomes**, not proof that the cluster/worker is safe or healthy. Persist an independent postcondition verdict from actual authorized provider read-back. Unknown/partial failure must stay Unknown/Failed pending recovery, never be represented as successful by optimistic UI.

## 4. Automation repository proposal

**Accepted operator decision (2026-11-15):** `OXY7O/kaori-operations` is the dedicated Git authority for operational automation source; the repository exists. Its current visibility is **public**, so real infrastructure inventory, secrets, credentials, kubeconfig, private topology or sensitive internal procedures must not be committed. The initial read-only source and tests are tracked by `OXY7O/kaori-operations#1` / Draft PR #2. This decision is not authorization to create a production cluster.

```text
kaori-operations/
  ansible/
    playbooks/
    roles/
    collections/
    inventory/examples/         # schema/sample only — NO private hosts or secrets
  kubernetes/self-managed/
    kubespray/                   # pinned upstream source reference/compatibility metadata
    provisioning/
    maintenance/
    verification/
  execution-environments/       # reproducible build definitions and digests
  runbooks/
  tests/
  docs/
```

**Inclusion rule:** operational automation *source* and testable operational runbooks across approved domains. **Exclusion rule:** KAORI application/model/routes/UI, real inventories and credentials, mutable runtime artifacts/logs, binary EE images, arbitrary personal scripts, full vendor-source fork, and live infrastructure state.

Pin and record repository identity, commit SHA, upstream Kubespray release/commit, Ansible/collection versions, execution-environment image digest, target host inventory snapshot/identity, approved profile, requester/approver, Plan/preflight signature, execution event digest, verification timestamp and authority. **Never execute a mutable branch tip without resolving and freezing a commit.**

## 5. Governed operation sequence

```text
Observe committed target state
→ qualify source, scope and privileged actor
→ resolve exact Git + EE identity
→ Plan & impact/preflight (check/diff only where supported)
→ review + maker/checker approval + maintenance window
→ refresh target state and reject stale/changed target/preflight
→ resource-scoped execution lock + canonical JobExecution
→ Ansible operation in isolated worker
→ trusted Kubernetes API / host read-back
→ commit verified result + audit + fresh inventory observation
→ release lock or record explicit intervention/recovery
```

For provisioning, validate OS/support matrix, clock sync, DNS/reachability, privileged SSH host-key trust, swap/firewall requirements by approved upstream version, network CIDR overlap, control-plane endpoint, VM resources and candidate CNI/CRI. Check mode may be partial: do not claim complete dry-run support when upstream modules do not support it.

For worker OS patching, verify spare scheduling capacity and PodDisruptionBudgets before cordon/drain, then run scoped package operations, reboot only when required, verify node Ready, network/storage/workload readiness and uncordon. Failed drain/patch/reboot keeps the node in a safe explicit state; automatic uncordon must not hide unknown health.

For future cluster upgrades, validate supported minor-version path, etcd backup/recovery, control-plane quorum, add-on/CRI/kubelet compatibility, per-node ordering, disruption budget and user-approved stop conditions. **Do not promise generic in-place version downgrade as rollback.**

## 6. Bounded implementation workstreams

1. **#4799 — IA execution foundation:** register provider/execution instance and Git source; secure credential references; dedicated worker route; read-only connectivity/facts pilot; canonical JobExecution/event redaction and tests. Extend existing Integration Kernel instead of a new provider framework.
2. **#4800 — Self-managed provisioning readiness:** define approved, version-locked Kubespray profile, existing-host inventory adapter, preflight support matrix and verified non-mutation Plan; negative authorization/network/secret tests.
3. **#4801 — Non-production create & verify:** approved provision run, Kubernetes API qualified registration/binding, inventory synchronization, independent cluster health assertions, audit and exact-candidate UAT.
4. **#4802 — Single-worker maintenance:** bounded drain → OS patch → conditional reboot → health check → uncordon with failure-safe controls, PDB and capacity gates.
5. **Future lifecycle:** Kubernetes version upgrade, control-plane maintenance, node replacement, schedules/compliance and managed-provider adapters under distinct implementation authorities.

Each workstream needs an issue-first branch, tests mapped to existing Gherkin/pytest where available, a protected isolated real-provider UAT target, and explicit Human Acceptance before any production use. No external mutation may be inferred as authorized from #4796.

## 7. Pilot acceptance and negative evidence

- Register/read-only discover existing hosts with explicit SSH host-key policy; invalid credential, unreachable host, untrusted host key and revoked scope must not cause mutation.
- Freeze a source commit + EE digest and show exactly what target/operation would execute; stale Plan or changed inventory must require renewed preflight/review.
- Reject unauthorized actor, missing approval, conflicting concurrent Run, outdated source and out-of-window maintenance request without side effects.
- Provision one non-production self-managed cluster through the **approved** adapter only after infrastructure mutation authorization; prove Kubernetes API reachability and correct Kubernetes Integration binding, not only runner exit code.
- Patch one non-production worker with safe cordon/drain + PDB handling, package manager execution, conditional reboot and post-change node/workload read-back. Preserve a truthful partial/unknown result if verification fails.
- Track exact Git SHA / worker image digest / candidate environment, sanitized logs/events, real provider read-back, committed evidence, Activity Audit and scenario-to-test mapping.

Architecture assessment alone is not a test PASS. Official Developer Check, Full Admission, production activation and deployment remain **HOLD** until separately authorized.

## Public source licensing and access authority

Operator decision: keep `OXY7O/kaori-operations` public as reusable **source** only. A public repository does not confer a reusable open-source license. Current `OXY7O/KAORI` `LICENSE` is the proprietary **KAORI INTERNAL USE LICENSE**. Rights-holder approval is required before introducing an Apache-2.0 (recommended for broad reusable community automation) or other license, accepting external contributions under a defined license, or copying KAORI proprietary source into the public repo. No license change is authorized by this design document.

Public source security baseline: `OXY7O/kaori-operations#3` / Draft PR #4. Public Kubespray compatibility-only profile: `OXY7O/kaori-operations#5` / stacked Draft PR #6, pinned upstream `v2.32.0` at `9751ea6f63244e433a7a6263d9ecf381e57bb8e9`; `execution_enabled=false`, `mutation_authorized=false`. KAORI static Plan qualification: #4800 / Draft PR #4811. Current development-only read-only localhost Celery/Runner source: #4799 / Draft PR #4807. These review candidates are not admitted production capabilities and not evidence of real Kubernetes UAT.

Never place credential material, real inventory, private network topology, cluster kubeconfig, or runtime event artifacts in the public source repository. The secrets/inventory and operator RBAC authority remains external to Git, and an approved Kubernetes execution remains a separately governed `JobExecution` with independent provider read-back.
