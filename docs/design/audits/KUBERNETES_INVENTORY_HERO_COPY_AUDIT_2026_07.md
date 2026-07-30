# Kubernetes Inventory Hero Copy Audit — July 2026

## Scope

Inventory Overview, Nodes, Namespaces, Workloads, Pods, Services, Ingresses,
Storage, Configuration, and Topology.

## Finding

All pages used the canonical `page_hero` geometry, but several descriptions and
right-panel metric helpers exceeded the intended content density. Component reuse
alone did not guarantee concise copy.

## Correction

- descriptions now use 7–12 words;
- repeated committed-snapshot wording was removed because Snapshot Context owns it;
- right-panel titles use two to four words;
- straightforward metrics use label + value only;
- explanatory helper sentences were removed from Inventory hero metric cards;
- Topology uses Relationships and Hidden Resources as direct graph metrics.

## Guardrail

`test_inventory_hero_copy_density_contract.py` enforces the Inventory hero copy
budget so later page changes cannot reintroduce verbose descriptions or metric
mini-paragraphs.
