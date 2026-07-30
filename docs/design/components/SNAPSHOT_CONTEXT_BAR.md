# Snapshot Context Bar

## Purpose

Use the Snapshot Context Bar when a page renders data from one committed, archived, or worker-generated snapshot and users must understand when, from where, and for which scope the data was produced.

Shared implementation:

```text
app/templates/components/snapshot_context_bar.html
```

## Canonical Content

The component owns:

1. snapshot title and semantic status;
2. concise freshness or coverage interpretation;
3. snapshot source;
4. latest collected timestamp;
5. active scope;
6. committed coverage;
7. snapshot exceptions such as stale or missing collections.

Exact collection timing and coverage belong here, not in the page hero.

## Visual Contract

- one compact `rounded-xl` bordered surface;
- a 4/8 responsive composition on wide screens;
- 16 px outer padding and a 36 px Violet-soft leading icon;
- `text-base font-semibold` snapshot title with an inline borderless status label;
- one concise sentence-case interpretation;
- snapshot source rendered as inline metadata rather than a second nested surface;
- four compact neutral metrics in one desktop row and a 2×2 responsive grid;
- no arbitrary font sizes, tracking, page-local status geometry, or decorative metric icon tiles.

The four canonical metrics are:

```text
Latest Collected
Active Scope
Committed Coverage
Snapshot Exceptions
```

## Usage Boundary

Appropriate for:

- Kubernetes Inventory snapshots;
- archived report snapshots;
- worker-materialized governance datasets;
- other read-only datasets with a committed generation boundary.

Do not use it for live provider health, transient request progress, or a general KPI row. Do not repeat its timestamp, freshness, or coverage values in the hero.


## Density Rule

The bar is context, not a dashboard KPI section. Keep it visually compact enough to sit between the hero and the primary catalog without becoming a second hero. Do not add a separate eyebrow row, source card, large metric tiles, progress visualization, or repeated freshness explanation.
