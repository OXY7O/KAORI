# Object Storage Inventory Pattern v1.1

Object Storage Inventory is a committed-snapshot workspace. Provider registration and validation remain owned by Integrations → Storage; inventory pages never query the provider API live.

## Setup prerequisite

`ObjectStorageSystem` is the canonical managed asset created by a registered Storage integration. When no managed system exists, Object Storage Inventory is setup-blocked rather than rendered as a normal empty inventory.

Blocked composition:

1. Canonical Hero remains visible.
2. Hero metadata uses `Committed Inventory` + `Object Storage Setup Required`; zero asset counters are not presented as evidence.
3. Hero right panel uses `Inventory Readiness / Object Storage Setup Required` with `Registered Systems = 0` and `Workspace State = Blocked`.
4. The setup banner directs authorized operators to Integrations → Storage.
5. Inventory Data Snapshot, posture/summary cards, filters, tables, and detail surfaces remain hidden.
6. Direct HTMX inventory reads return the setup banner while blocked.

A registered system with no committed inventory is **not** setup-blocked. It is a collection-pending inventory state and must continue to expose the Inventory Data Snapshot with missing/partial collection evidence.

## Inventory Data Snapshot

Overview, Systems, and Buckets & Containers all place the canonical `Inventory Data Snapshot` immediately below the Hero in ready state. It reports committed source, freshness, active scope, system coverage, and snapshot exceptions using `components/snapshot_context_bar.html`.

## Overview composition

The ready-state Object Storage Inventory Overview uses the shared Inventory Overview reading order:

```text
Hero
→ Inventory Data Snapshot
→ Fleet Inventory Posture
→ Object Storage Asset Catalog
```

`Fleet Inventory Posture` and `Inventory Assets` retain their shared plain `section_intro.html` heading/description hierarchy outside the content blocks. Following explicit human DevContainer review in #946, both content groups intentionally use **one** shared `operational_section_card.html` each rather than flat callouts or nested shells:

- `Fleet Inventory Posture` → `Object Storage Fleet Evidence` → shared `resource_posture_grid.html` with **four** committed signals (quota assessment, protection attention, public exposure, optional usage evidence). Metric labels/values stay separate within the shared grid and preserve evidence-qualified tones. No collected assets produce `No Evidence`, not a fabricated normal/zero state.
- `Inventory Assets` → `Object Storage Asset Catalog` → dynamic `2 Asset Types` badge plus two shared `inventory_asset_card.html` links (Systems and Buckets & Containers) in the responsive two-column grid.

The four metrics remain domain-owned, not mechanically copied from Registry. Green clean-state protection or public exposure requires complete corresponding committed control evidence; partial or unknown evidence is explicitly qualified, never interpreted as compliance. There is **no additional outer section-card shell** around the two approved content cards. `docs/design/patterns/KUBERNETES_INVENTORY_OVERVIEW.md` and #946 are the review authority for this current composition.

Systems and Buckets & Containers reuse the canonical Inventory Resource Page hierarchy:

```text
Inventory Data Snapshot
Operational Posture — shared Section Intro
└── System / Namespace posture block
Inventory Records — shared Section Intro
└── Shared Inventory table
```

The section title and supporting description sit outside the posture/table box. Existing `resource_posture_grid.html`, `operational_section_card.html`, and shared table primitives remain authoritative.

## Ownership

- Integrations → Storage: registration, configuration, validation, runtime health.
- Jobs & Executions: Object Storage Inventory Sync scheduling and execution.
- Object Storage Inventory: committed systems/buckets/containers evidence only.
- Object Storage Analytics: live/metric-derived analysis after inventory and metrics dependencies are eligible.

## Detail standard

Overview, Systems, and Buckets & Containers use the shared `components/resource_detail_modal.html` host and Unified Resource Sheet V10. Overview reuses the canonical System detail endpoint instead of rendering a second inline drawer implementation. Detail surfaces remain committed-snapshot reads, use one modal-body scrolling context, and do not create nested vertical scrolling regions for provider evidence or metadata collections.
