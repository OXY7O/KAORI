# Inventory Resource Page Pattern

## Reference

Kubernetes Node Inventory is the first canonical implementation.

## Structure

```text
Canonical Hero
Compact Snapshot Context Bar
Resource Posture Section
Filtered Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Ownership

- Hero: resource identity, active scope, and high-level health posture.
- Snapshot Context Bar: source, exact collection time, committed coverage, and exceptions.
- Resource Posture: capacity and domain-specific operational evidence.
- Table: compact comparison and one row detail action.
- Full Workspace Modal: complete resource evidence and operational context.

## Table rules

- Prefer grouped columns over one column per related metric.
- Technical identifiers use `technical_value.html`.
- Metadata such as Node role uses `metadata_label`.
- Operational state uses borderless status or status-indicator labels.
- Pagination shows resource-aware copy and a visible `Rows` label.

## Data boundary

All list, summary, and detail views read the latest committed inventory generation. Detail requests are on demand and must not trigger a live Kubernetes API request.


## Namespace implementation

Namespace Inventory is the second canonical implementation. It uses Namespace Control Posture, a governance-focused compact table, Technical Metadata Collection, and neutral factual evidence when no explicit governance policy is available.

## Workload implementation

Workload Inventory is the third canonical implementation. It separates semantic operational posture from type-specific factual state, uses a compact namespaced table, Related Resource Collection for associated Pods, and neutral factual treatment for workload configuration.

## Pod implementation

Pod Inventory is the fourth canonical implementation. It separates operational state from Kubernetes phase/readiness evidence, uses the shared Container Runtime Collection, exposes configuration and storage references, and treats Pod configuration as factual evidence until an explicit policy evaluates it.
