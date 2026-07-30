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

- one `rounded-xl` bordered surface;
- a 5/7 responsive composition on wide screens;
- a 44 px Violet-soft leading icon;
- `text-base font-semibold` snapshot title;
- borderless semantic status label;
- a dedicated source strip on the left;
- four neutral context metrics in a 2×2 grid;
- no arbitrary font sizes, tracking, or page-local status geometry.

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
