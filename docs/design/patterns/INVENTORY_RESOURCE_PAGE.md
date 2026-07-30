# Inventory Resource Page Pattern

## Reference

Kubernetes Node Inventory is the first canonical implementation.

## Structure

```text
Canonical Hero
Compact Snapshot Context Bar
Resource Posture Section
Filtered Inventory Table
Detail Style 1 — Inline Expanded Detail
```

## Ownership

- Hero: resource identity, active scope, and high-level health posture.
- Snapshot Context Bar: source, exact collection time, committed coverage, and exceptions.
- Resource Posture: capacity and domain-specific operational evidence.
- Table: compact comparison and one row detail action.
- Inline Detail: complete resource evidence and operational context.

## Table rules

- Prefer grouped columns over one column per related metric.
- Technical identifiers use `technical_value.html`.
- Metadata such as Node role uses `metadata_label`.
- Operational state uses borderless status or status-indicator labels.
- Pagination shows resource-aware copy and a visible `Rows` label.

## Data boundary

All list, summary, and detail views read the latest committed inventory generation. Detail requests are on demand and must not trigger a live Kubernetes API request.
