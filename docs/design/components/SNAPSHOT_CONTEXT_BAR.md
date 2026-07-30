# Snapshot Context Bar

## Purpose

Use the Snapshot Context Bar when a page renders data from one committed, archived, or worker-generated snapshot and users must understand when, from where, and for which scope the data was produced.

Shared implementation:

```text
app/templates/components/snapshot_context_bar.html
```

## Canonical Content

The bar owns four information groups:

1. source and semantic snapshot status;
2. latest collected timestamp;
3. active scope;
4. committed coverage.

The description explains any freshness or coverage limitation in one concise sentence.

## Visual Contract

- one `rounded-xl` bordered surface;
- one 40 px Violet-soft context icon;
- source title uses `text-base font-semibold`;
- description uses shared body hierarchy;
- status uses the borderless semantic status-label component;
- context values use three neutral `rounded-lg` cells;
- no arbitrary font sizes, tracking, or page-local status geometry.

## Usage Boundary

Appropriate for:

- Kubernetes Inventory snapshots;
- archived report snapshots;
- worker-materialized governance datasets;
- other read-only datasets with a committed generation boundary.

Do not use it for live provider health, transient request progress, or a general KPI row.
