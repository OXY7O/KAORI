# Canonical Linux Host Inventory Intent — Infrastructure Automation (#5161)

Authority: #556 / #4796 / #5155 / #5161, with SSH and secret admission under #5162 and immutable Plan adoption under #5163/#4800. Existing Kubernetes `NodeInventory` is observed from the authoritative Kubernetes API after cluster creation and is not used for pre-provision Linux VM/bare-metal registration.

## Persistence and scope

- `AutomationHostAsset` owns a stable KAORI UUID, canonical name, nonproduction environment, bounded RFC1918 management IP and SSH port, lifecycle and timestamps. It stores **no credential material**. The unique environment+name and environment+IP constraints avoid ambiguous host identity.
- `AutomationInventoryAssignment` associates an existing canonical Ansible `IntegrationInstance` with one of those hosts under an explicit Kubernetes Lifecycle control-plane/worker role, not a separate Ansible/provider inventory database.
- The `AutomationHostIntent` service normalizes fixed, nonproduction RFC1918 addresses and denies production, public/multicast/link-local/loopback, non-IP URL, invalid names and invalid ports. The Ansible connection must be an active, exactly environment-matched canonical source instance. Register and assign commit through existing SQLAlchemy with rollback on error.
- `preview_inventory_intent` derives a deterministic sha256 correlation fingerprint from scoped canonical host identity, role, IP and SSH port. It **never returns IP/name or private inventory**, never gives a signed approval/Run token and always returns `execution_authorized=False`. Changes to identities/endpoints/roles change the fingerprint. Missing, duplicate, disabled, cross-instance or invalid observations fail closed. The report has state `requires_trust_admission`, not Ready.
- This is a persistence and read-only fingerprint seam, not a remotely executable inventory file or post-provision Kubernetes API evidence. No user-visible Ansible Runner, SSH, Kubernetes mutation route is introduced by this issue.

## Relationship ownership and pilot network scope

This inventory-intent record is **not** a second `IntegrationBinding` for a Kubernetes cluster. Under #4845, canonical `IntegrationBinding(asset_type=kubernetes_cluster)` is the sole relationship between Ansible and an observed KAORI Kubernetes `Cluster`. `AutomationInventoryAssignment` is instead **pre-provision execution-target group intent** (the desired control-plane/worker membership of existing Linux VM/bare-metal assets); it is not a consumer binding, does not establish Kubernetes existence, and cannot satisfy the #4845 Cluster binding or #4801 Run gate. The eventual Kubernetes API `NodeInventory` is independently observed after cluster creation. Do not mirror `AutomationInventoryAssignment` records into `IntegrationBinding` to claim an operational cluster.

For this first non-production pilot, unique `(environment, address)` identifies a host only inside one explicitly approved network scope. The conservative constraint **rejects** reuse of the same RFC1918 address in two overlapping networks of one environment; it does not falsely merge those two hosts. Multi-site onboarding with overlapping RFC1918 address spaces requires a future site/network-scope authority, updated DB constraints and independent asset correlation under #712 **before** accepting those sites. A mere hostname/IP match must never automatically merge asset identities.

The current Python host registry has no HTTP registration route, RBAC/CSRF grant, secret retrieval or worker dispatch. Registration via any future operator action requires scoped permissions, audit and source-owned SSH trust under #5162. The assignment's state remains operator intent, not proof of independent access or execution approval.

## Admission and next dependency

#5162 must attach approved Secrets & PKI credential **reference**, independently trusted SSH host-key fingerprints, and fresh read-only remote facts/EE authority before any host can become admissible. #5163 consumes the validated immutable inventory snapshot in canonical `JobExecution` Plan materialization. #4801 requires maker/checker approval, approved window and independent Kubernetes API read-back before actual cluster changes. Source SHA, EE digest, targets and inventory fingerprint must be revalidated immediately before any eventual worker Run.

Schema revision `20261123_automation_hosts` depends on existing `20261112_internal_pki`. Validate using the canonical `verify_migration_graph.py` and full PostgreSQL migration/rollback before stage UAT. Do not infer staging backup/restore or schema migration success from CI alone.
