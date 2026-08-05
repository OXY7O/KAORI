# Kubernetes Node Inventory Alignment Audit — August 2026

## Scope

Reviewed:

- route and filter behavior;
- committed-snapshot query boundary;
- Hero and Snapshot Context Bar;
- posture metrics;
- compact inventory table;
- full workspace detail;
- dark-mode semantic tokens;
- responsive/HTMX behavior;
- accessibility;
- documentation and quality-gate coverage.

## Assessment

The page already used the correct high-level KAORI structure and did not require a visual redesign. The audit found several correctness and presentation drifts that could make an otherwise polished page misleading or inconsistent.

## Findings and corrections

### 1. Fleet posture represented readiness only

**Before:** the Hero context was titled `Node Fleet Posture`, but its status was calculated only from `Ready`/`NotReady`. A Ready node with pressure, a network issue, or a cordon could still produce `Healthy`.

**Correction:** added a fleet-posture resolver that includes readiness, network availability, pressure, scheduling, and unknown readiness evidence. The context metrics are now Ready and Active Signals.

### 2. Missing capacity evidence was silently converted to zero

**Before:** missing CPU, memory, and ephemeral-storage values participated in totals as zero. The page did not expose source coverage.

**Correction:** each capacity metric now has a reported-node count, semantic coverage tone, explicit `Not Available` state, and `Reported by X of Y filtered nodes` supporting copy.

### 3. Filter labels exposed raw Kubernetes values

**Before:** Role and Status options could display `control-plane` and `NotReady`.

**Correction:** request values remain canonical, while labels are normalized to `Control Plane` and `Not Ready`. Added explicit label/input association and an accessible filter-form name.

### 4. The compact table hid operational conditions

**Before:** the row showed readiness but not cordon, pressure, or network evidence. Users had to open every detail record to identify the active signal counted by the Hero.

**Correction:** a concise condition summary now appears below the readiness indicator, capped at two labels plus `+N more`. The seven-column table remains unchanged.

### 5. Table semantics were incomplete

**Before:** header cells had no explicit column scope and the table had no accessible caption.

**Correction:** added `scope="col"` and a scope-aware screen-reader caption.

### 6. Detail cards repeated their own first value

**Before:** Node Identity repeated Age in its badge and row; Node Capacity repeated CPU; Platform & Runtime repeated Operating System.

**Correction:** removed redundant badges while preserving factual rows.

### 7. Connectivity contained unrelated placement data

**Before:** Scheduled Pods appeared inside Connectivity even though it already existed in the summary.

**Correction:** Connectivity now contains Internal IP, External IP, Hostname, and Network Scope only.

### 8. Taints and labels used local presentation

**Before:** taints were rendered as many Violet metadata pills and Node Labels had a page-local section implementation.

**Correction:** taints use neutral technical-value surfaces; Node Labels use the shared Technical Metadata Collection.

### 9. Unknown readiness could receive a healthy action

**Before:** a node with unknown readiness and no reported pressure could fall through to `Node Ready for Scheduling`.

**Correction:** unknown readiness now produces `Validate Node Readiness Evidence` with Unknown semantic tone.

### 10. Source wording implied live collection

**Before:** the table header description said nodes were collected from connected clusters without naming the committed boundary.

**Correction:** wording now explicitly states `Latest committed Kubernetes node records`.

### 11. HTMX filters left Hero and snapshot scope stale

**Before:** filter requests replaced only the resource posture and table. Cluster,
role, readiness, or search changes could leave Hero totals and Snapshot Context
describing the previous scope.

**Correction:** Node filter changes now replace the complete
`#nodes-page-workspace`; pagination remains table-only.

### 12. Incomplete Node status evidence removed the Node entirely

**Before:** collection skipped a Node when `status` or `status.node_info` was
missing, hiding the asset instead of presenting explicit Unknown/Not Reported
evidence.

**Correction:** collection preserves every named Node and records missing status,
runtime, platform, capacity, and scheduling values explicitly.

### 13. Capacity totals accumulated per-node rounding error

**Before:** memory and ephemeral-storage values were rounded to one decimal before
fleet aggregation.

**Correction:** source precision is retained during aggregation and rounded only
after the fleet total is complete.

### 14. Legacy control-plane roles produced duplicate filters

**Before:** clusters containing both `master` and `control-plane` role labels
rendered two indistinguishable `Control Plane` options.

**Correction:** both stored values map to one canonical `control-plane` request
filter while matching both legacy and current records.

## Files changed

```text
app/inventory/resources/nodes.py
app/inventory/routes.py
app/templates/components/table.html
app/templates/inventory/nodes/partials/_hero.html
app/templates/inventory/nodes/partials/_summary_cards.html
app/templates/inventory/nodes/partials/_table_card.html
app/templates/inventory/nodes/partials/_table_content.html
app/templates/inventory/nodes/partials/_node_detail_content.html
docs/design/patterns/KUBERNETES_NODE_INVENTORY.md
docs/design/audits/KUBERNETES_NODE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md
scripts/verify_node_inventory_standard.py
tests/contracts/kubernetes/test_node_inventory_standard_contract.py
```

## Disposition

- Visual composition: retained.
- Data semantics: corrected.
- Shared-component ownership: strengthened.
- Accessibility: strengthened.
- Legacy July audit: historical record only.
- Canonical standard: `docs/design/patterns/KUBERNETES_NODE_INVENTORY.md`.
