# KAORI Kubernetes Inventory — Dev Container Human UAT & Gherkin Evidence

**Authority:** #733 (Kubernetes Inventory UAT), #1690 (Topology dense viewport), and the approved Inventory/Topology design patterns.  
**Scenario specification authority:** #1738 / `docs/engineering/uat/features/inv-kubernetes-inventory.feature` on its QA work branch.  
**Human decision:** **UAT APPROVED** by the operator on **2026-10-25 (Asia/Jakarta)** for the manually reviewed Inventory scope listed below.  
**UAT aggregation branch:** `kaori/review/staging-uat` (temporary holding branch, not a promotion to `kaori/staging`).  
**Execution provenance:** Browser screenshots, operator confirmations and focused test console outputs supplied in KAORI's Dev Container UAT conversation during 2026-10-24–25. The final confirmation did not report a fresh `git rev-parse HEAD`; do not attribute those test logs to the documentation commit or assume they cover a frozen official candidate.

## Acceptance and quality-gate separation

- **Human Visual + Functional UAT: APPROVED for the reviewed Kubernetes Inventory workflows.** Human confirmation included Overview, Node, Namespace, Workload, Pod, Service, Ingress, Storage, Configuration and Topology.
- **Last focused Topology regression provided by operator:** `tests/contracts/kubernetes/inventory/test_topology_dense_viewport_contract.py` → **4 passed in 1.53s**; `djlint --check app/templates/kubernetes/inventory/topology/partials/_workspace.html` → **PASS (0 files would be updated)**.
- **Outstanding check:** `npx prettier --check app/static/js/kubernetes/inventory/topology.js` → **WARN (formatting issues)**. The latest message does **not** prove Prettier clean. Do not mark Developer Check, Full Admission, static quality or final release ready until it passes; formatting is a quality issue, not a retraction of the explicit human UI acceptance.
- **Earlier CSS evidence:** `npm run build-css` and `npm run verify-css` passed Violet/neutral dark tokens on the preceding reviewed Topology candidate, not independently rerun in the latest operator message.
- **Not individually executed:** full six-viewport × two-theme matrix for each Inventory page, direct authorization bypass, missing/stale/partial snapshots for every resource kind, malicious values/log/database/export assertions, all 350-node graph-limit conditions, negative cluster identity/recreated UID, and full automated Scenario-ID/JUnit attribution. They remain owned by existing contract/security/UI and official admission gates.

## Scope-by-scope human evidence

| Scope | Manually reviewed evidence | Human status |
| --- | --- | --- |
| Overview | Fleet snapshot, eight asset categories, cluster comparison table and full cluster detail; committed evidence boundary | APPROVED |
| Nodes | Node posture, Ready/role/search filtering, detail sections and metadata; Close/reopen/Escape | APPROVED |
| Namespaces | 25 namespaced records, quota/limit/NetworkPolicy/PSA context, details, lifecycle filter and pagination/reset | APPROVED |
| Workloads | 32 records, 31 controller + 1 batch, `vault` Progressing example, namespace/state filters, detail, reset and Escape | APPROVED |
| Pods | 40 records, one Not Ready signal, restart/ownership evidence, Ready and Succeeded examples, search and detail | APPROVED |
| Services | 45 records, 44 ready backend registrations and one exception, `LoadBalancer` filter, selector/endpoint/port details, clear/reset and modal Close/Escape | APPROVED |
| Ingresses | Two records, three declared hosts and three routes, `nginx` + no TLS, host/backend evidence, reset and modal Close/Escape | APPROVED |
| Storage | 2 StorageClasses + 10 PV + 10 PVC = 22 objects, Bound PV/PVC pair, capacity/binding/related claims and Mounted Pods, reset and modal behavior | APPROVED |
| Configuration | 58 ConfigMaps + 46 Secrets = 104, key-names-only modal, Secret metadata boundary, collected timestamps reconciled after refresh, reset and Escape | APPROVED |
| Topology | Depth 1 graph and Resource List, 3 CL/NS/ND records, right inspector Details/Relationships, Full-depth Hierarchy/Dependency and dense readability remediation, Fit, focused viewport hint and compact one-line copy | APPROVED after iterative review |

**Important interpretation:** `Ready`, `Bound`, `Published`, `Connected`, `Current` and `Collected` are evidence-qualified operational labels. They do **not** independently prove live provider reachability, application availability, external DNS, certificate validity, filesystem durability, or continuous sync. ConfigMap/Secret values must never be indexed, decoded, persisted, logged, rendered or exported by the Inventory projection; the manual UI confirms visible key-only behavior, while implementation-level persistence/denial assertions require separate security evidence.

## Gherkin — manually reviewed positive scenarios

The scenarios below document the **operator's observed paths**, not a new executable Cucumber suite. Keep reusable stable `UAT-INV-001`–`005` tags and the full negative/specification catalog under #1738; do not invent new Scenario IDs or mark its machine execution matrix PASS from these screenshots.

```gherkin
Feature: Kubernetes Inventory — Dev Container human acceptance
  The KAORI Inventory reads current committed Kubernetes generations,
  provides scope-consistent resource evidence, and delegates execution to
  the authoritative Kubernetes provider and approved Operations workflows.

  Background:
    Given an authorized KAORI operator uses the Kubernetes X300 Development cluster
    And the Inventory has a selected fully committed snapshot
    And normal Inventory requests do not require live Kubernetes API reads

  Scenario: Fleet Overview presents committed coverage and resource entry points
    When the operator opens Kubernetes Inventory Overview
    Then the Hero and Snapshot Context identify the committed cluster and collection
    And the eight resource categories show normalized committed counts
    And the cluster table uses five rows by default and opens cluster details
    And the detail modal distinguishes collection health from live provider readiness

  Scenario: Node and Namespace tables retain filter and relationship semantics
    When the operator filters Node role and searches for an absent node name
    Then the table presents an honest no-result state with Clear Filters
    When the operator resets filters and opens a Node detail
    Then identity, capacity, network, conditions and committed metadata are shown
    And Close and Escape each dismiss the reopened modal
    When the operator filters Namespace lifecycle and moves to another page
    Then the selected lifecycle remains visible and namespace rows stay scoped
    And clearing filters returns the default lifecycle and first page

  Scenario: Workload and Pod records preserve owner, state and runtime evidence
    When the operator filters Workloads to namespace capsule-system
    Then two scoped Workload records remain and Clear Filters restores 32 records
    When the operator filters Workloads to Progressing and opens the vault StatefulSet
    Then the detail shows the committed desired and ready replica state
    And Pod template, scheduling, container images and metadata are source-qualified
    When the operator examines Pods with Ready and Succeeded lifecycle examples
    Then runtime readiness, owner type, placement and restart evidence remain distinct
    And searches, pagination and modal Close/Escape preserve current scope

  Scenario: Service and Ingress detail distinguish declared configuration from reachability
    When the operator opens Services and filters by LoadBalancer
    Then the matching Service retains declared access, ports and registration evidence
    When the operator opens a Service detail
    Then backend registration, traffic settings, port mappings and endpoints are visible
    And Clear Filters restores 45 Services and the modal closes with Close or Escape
    When the operator opens Ingresses and selects class nginx with no TLS declaration
    Then the two records retain their published controller address and declared hosts
    And a selected Ingress detail shows identity, route and backend references
    And no missing TLS reference is silently treated as a verified certificate
    And Clear Filters restores both unfiltered Ingress records

  Scenario: Storage relationships retain StorageClass PV and PVC identity
    When the operator filters Storage to StorageClass
    Then hostpath and standard are shown as Configured, not Bound volumes
    And the StorageClass detail shows provisioner and WaitForFirstConsumer binding
    When the operator resets the Storage filter
    Then all 22 Storage records become available again
    When the operator opens a Bound PV and its matching PVC
    Then capacity, binding references, related claims and mounted Pods agree
    And each resource modal supports Close, reopening and Escape

  Scenario: Configuration shows protected key indexes without data values
    When the operator opens Configuration Inventory
    Then 58 ConfigMaps and 46 Secrets are represented by committed metadata
    When the operator filters ConfigMaps and opens capsule-crds-capsuleconfigurations
    Then the key name content is indexed without rendering its value
    And mutation state and collected Pod references are source-qualified
    When the operator refreshes and reopens the same object
    Then Latest Collected and detail collection context agree
    When the operator selects Secret and opens a Secret detail
    Then only Secret type, key names and permitted metadata are visible
    And clearing filters returns 104 Configuration records
    And the detail modal dismisses with Close and Escape

  Scenario: Topology explores committed relationships with readable fallback
    When the operator opens Topology at one relationship level
    Then cluster, namespace and scoped node identities agree in Graph and Resource List
    When the operator selects Kubernetes X300 and opens its Details inspector
    Then cluster identity and committed properties are shown
    And Relationships shows two outbound Contains entries for the visible scope
    When the operator chooses Full Relationships and changes the layout mode
    Then Hierarchy View and Dependency View retain the same committed resource identities
    And the focused viewport offers readable local exploration
    And Fit represents the complete visible graph as a separate overview
    And a compact single-line hint distinguishes focus from overview
    And Resource List remains usable when the dense overview cannot show every label
```

## Traceability to canonical QA catalog

| Canonical ID | Coverage association | Machine execution attribution |
| --- | --- | --- |
| `UAT-INV-001` | Fleet overview, resource list/detail and scoped modal evidence | NOT RUN as an exact-ID scenario |
| `UAT-INV-002` | Snapshot freshness semantics, missing/partial negative cases | NOT RUN for negative fixtures |
| `UAT-INV-003` | Recreated object UID and cross-generation identity negative case | NOT RUN |
| `UAT-INV-004` | Shared filters, pagination, no-results and Clear Filters; observed positive UAT subset | NOT RUN as exact-ID machine scenario |
| `UAT-INV-005` | Topology graph/source relationship absence or inconsistency negative case | NOT RUN for negative fixtures |

**Execution distinction:** the operator's explicit Inventory Human Acceptance applies to the reviewed positive behaviors in this document. It does not retroactively turn all five canonical specifications, including the untested negative scenarios, into machine PASS. This artifact is an audit record for the accepted manual session and a source of focused regression requirements—not a second QA catalog or a new test runner.

## Governance and next quality checks

**Current flow:** Issue #733 + child #1690 → reviewed implementation on temporary `kaori/review/staging-uat` → **Human UAT ACCEPTED** → outstanding static-formatting clean-up and official gates **HOLD** until explicitly authorized. No direct changes to `main`, no `kaori/staging` promotion, no release/tag.

Before official admission, rerun on the exact candidate:

```bash
git rev-parse HEAD
python -m pytest -q -p no:cacheprovider \
  tests/contracts/kubernetes/inventory/test_topology_dense_viewport_contract.py
npx prettier --check app/static/js/kubernetes/inventory/topology.js
djlint --check app/templates/kubernetes/inventory/topology/partials/_workspace.html
npm run verify-css
```

**Outstanding:** Prettier formatting warning, full formal Developer Check and Full Admission, targeted security/authorization and negative evidence matrix. The GitHub Project metadata must follow the existing KAORI taxonomy; connector support for changing Project custom fields must not be assumed.
