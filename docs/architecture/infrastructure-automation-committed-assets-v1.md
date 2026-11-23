# Committed Assets & Inventories review in Kubernetes Lifecycle (#5170)

Authority: #5168 (Assets & Inventories), #5157 Infrastructure Automation UI, #5161 canonical host persistence, #5155 inventory fingerprint and approved #556/#4796 Ansible/Kubespray architecture.

## Source/permission boundary

The existing `Operations Center → Infrastructure Automation → Kubernetes Lifecycle` selected connection can render five rows per page from the **committed** `AutomationInventoryAssignment` and `AutomationHostAsset` relationships. The existing `integrations.manage` route permission remains required, and host names, roles and RFC1918 endpoint/SSH ports are only queried and rendered when the signed-in principal also has `inventory.view`. Selections never traverse other Ansible connection IDs.

The read model loads no more than 257 committed membership rows for the selected instance and validates the **entire** bounded set with the existing `preview_inventory_intent` contract before paging. More than 256 members, mixed environments, invalid/retired/duplicate hosts, cross-connection assignments, or disabled/nonproduction-ineligible connections fail closed. Ineligible projections reveal neither endpoint rows nor inventory fingerprint. A SHA256 prefix is displayed for qualified **correlation** only; it is never a signed Plan, secret, admission token or Run approval.

Server pagination stays at **five entries per page** while ordinary connection pagination and HTMX selection continue to work. Jinja HTML escaping, shared table/action buttons/loading/semantic-status primitives, normal GET fallback and explicit empty/blocked/missing-permission states apply; no new menu route or UI component is invented.

## Explicit limitations

This PR does **not** implement Create/Edit/Retire or credential-reference forms, host/SSH trust verification, Vault material readback, Ansible Runner, cluster provisioning, Kubernetes NodeInventory derivation, or a second job ledger. Those require independent #5168/#5162/#4799/#4800/#4801 admission. `20261123_automation_hosts` still requires an approved staged PostgreSQL migration, backup/rollback and browser Human UAT under #5161/#5169. The card will show an honest blocked/empty state until committed inventory data exists; the presence of a row never implies that the host can be contacted.

No HTTP GET invokes SSH/Ansible/Secrets provider/Kubernetes operations. Keep `main` and all live cluster/runtime targets unchanged.
