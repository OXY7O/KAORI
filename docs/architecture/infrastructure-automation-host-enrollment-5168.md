# Infrastructure Automation — committed host enrollment (#5168)

This is the **source-only** operator host-identity lifecycle for approved
self-managed Kubernetes on pre-existing non-production Linux hosts. It extends
the accepted #5155/#5161 host identity schema, the existing #4834 Ansible
IntegrationInstance and #5157 Infrastructure Automation workspace. It does not
create another host/cluster provider or execution registry.

## Workflow and authority

1. **Integrations → Orchestration → Configuration Automation → Ansible**:
   the operator validates the immutable Git source and registers an Ansible
   source connection. It remains \`enabled=false\` until independent execution
   admission. A disabled *execution* connection may still display its valid
   committed host registration intent in Operations Center; this never
   authorizes SSH or Kubespray.
2. **Operations Center → Infrastructure Automation → Kubernetes Lifecycle**:
   after selecting the connection, an operator with both
   \`integrations.manage\` and \`inventory.view\` may use *Register Host & Role*.
   The server derives the environment from that connection and accepts only
   a validated private IPv4, canonical name, bounded port and
   \`control_plane\`/\`worker\` role. The browser cannot choose a different
   provider/connection by form field.
3. Enrollment creates \`AutomationHostAsset\` and
   \`AutomationInventoryAssignment\` in **one database transaction**; duplicate
   environment/name/address and 256-member overflow fail closed. A normalized
   operational event is emitted only after successful commit.
4. An authorized operator may **Edit** a single-instance host through the scoped
   detail route; its submitted revision must match current host and role state.
   A shared or stale host edit fails closed. The **Retire Host** route requires
   CSRF, an exact-name confirmation and POST; it disables the assignment and
   soft-retires the asset without deleting historical evidence. Retired records
   are excluded from the active inventory projection. No remote host is changed.
5. The existing committed read model computes the all-member active inventory
   fingerprint (including host name) then shows at most five rows per page. A source-only connection
   no longer blocks *review* on the basis of \`enabled=false\`, but the
   execution/readiness flags remain false.

## What is not yet accepted

This source-only registration is **not** the entire requested workflow:
existing-host assignment, shared-asset ownership policy and advanced host metadata are further #5168 work;
#5162/#4799/#5066 own usable secret references, trusted SSH, pinned worker/EE
and host facts; #5163/#4800 own immutable Plan and change approval; #4801
owns the *separately authorized* disposable non-production Kubespray apply and
independent Kubernetes API verification. #5172 is the single full-lifecycle
release/UAT gate. No new publicly deployed RC is justified by enrollment alone.

There are no raw credentials, arbitrary YAML, direct SSH calls, network
provider GETs or cluster mutation routes in this feature. User-visible Visual
QA, security/negative tests, the separate infrastructure mutation approval,
recovery and actual non-prod host UAT remain required.
