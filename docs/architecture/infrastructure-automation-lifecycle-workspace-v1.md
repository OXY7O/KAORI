# Infrastructure Automation → Kubernetes Lifecycle Workspace (v1)

Authority: #556 → #4796; Ansible registration #4834, read-only host evidence #4799, Kubespray preflight/Plan #4800, existing cluster binding #4845 and dedicated UI issue #5157. Infrastructure Automation is a capability under the **existing Operations Center navigation**, not an Ansible/Kubespray top-level menu. The first profile is Kubernetes Lifecycle using Kubespray; other profile adapters can use the same operational control plane when independently admitted.

## Separation of responsibilities

| Surface | Authority |
| --- | --- |
| Integrations → Orchestration → Configuration Automation → Ansible | Canonical `IntegrationInstance`, Git source, profile, connection/source validation, EE reference and four-tab Manage Connection |
| Operations Center → Infrastructure Automation | Permission-scoped, committed-state-only operational **projection** over the selected Ansible connection and future profiles; never provider mutation |
| Jobs & Executions | Canonical `JobExecution` status, queue, committed run evidence, retries and audit |
| Kubernetes Operations / Inventory | Existing `Cluster` and `NodeInventory` from independent Kubernetes API readback |
| `IntegrationBinding` | Exact connection-to-cluster association; not an execution permission |
| Infrastructure Automation host asset/inventory intent (#5155) | Pre-provision Linux host identity, SSH address/port, approved credential ref and immutable snapshot; *not* `NodeInventory` |

The workspace is registered as a nested `platform_operations.infrastructure_automation.index` GET at `/platform-operations/infrastructure-automation/` using the existing Operations Center navigation catalog, breadcrumb, Violet shared Hero/table/Guide/Registry/HTMX components, and `integrations.manage` admission. Ordinary GET reads only bounded canonical PostgreSQL state; there are **no** SSH/Ansible/Git/Kubernetes requests or infrastructure mutation buttons. `jobs.view` and `inventory.view` independently gate Jobs and cluster-binding projections; source connections are visible only with `integrations.manage`.

## Operator workflow

1. Configure the immutable Ansible/Kubespray Git source and its policy under **Integrations → Ansible → Choose → Add Connection → Manage Connection**.
2. Open **Operations Center → Infrastructure Automation** (or follow the connection detail action). The default five-row connection registry searches by canonical name, supports HTMX with full GET fallback, and shows committed source readiness without implying Run authority.
3. Review the existing 8/2 gate preflight, immutable review-only Plan currentness and optional canonical JobExecution history. A source-only or stale/unready connection remains **Blocked**.
4. Review committed Kubernetes associations only when permitted. A binding never manufactures Cluster or NodeInventory, and a committed cluster/node count is not proof of Ansible readiness or verified post-provision success.
5. Once independently approved future issues implement host registry (#5155), remote preflight and worker (#4799/#5066), and non-prod provision/verify (#4801), reuse this workspace; no alternate runner/job/inventory database.

## Compatibility and execution caveats

The 2026 five-year policy #473 governs **API visibility**, not all Kubespray operations. The separate exact-source operation qualification under #5156 must be adopted and UAT-tested before privileged Run controls are designed. Provision/Scale/Upgrade/Node Maintenance/Recovery remain blocked until source/EE/credential/SSH-host-key admission, immutable inventory, maker/checker, maintenance window, target lock, and independent Kubernetes API verification have succeeded. Neither a green source check nor a current review Plan authorizes mutation.

## QA

Use canonical Ruff, Ruff Format, djLint, Pyright, pytest, `verify_ui_reuse` and `verify_ui_style`, CI Developer Check and five Full Admission lanes on the exact issue head. On hosted staging, inspect light/dark and mobile/desktop, keyboard Guide, empty/query pagination/HTMX fallback, wrong identity/permission, stale preflight and Plan, and Jobs/inventory RBAC. Human Visual UAT and real non-production provider verification are separate from CI.
