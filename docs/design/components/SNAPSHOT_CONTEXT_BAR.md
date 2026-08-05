# Snapshot Context Bar Standard v1.1

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

The component is a **single neutral summary surface**, not a row of nested Violet cards.

- one compact `rounded-xl` bordered `surface-card` shell;
- a 4/8 responsive composition on wide screens;
- 16 px outer padding and one 36 px Violet-soft identity icon;
- `text-base font-semibold` title with one inline semantic status label;
- one concise sentence-case interpretation;
- source rendered as inline metadata rather than a nested source card;
- one neutral metric region separated from identity by a subtle divider;
- four transparent metrics separated by whitespace and desktop vertical dividers;
- Semantic color appears only on the status label and meaningful coverage/exception icons;
- no metric background tiles, gradient, nested shadow, or repeated Violet surface;
- light and dark mode use the same neutral-first hierarchy.

The four canonical metrics are:

```text
Latest Collected
Active Scope
Committed Coverage
Snapshot Exceptions
```

Each metric may provide one concise supporting line. Examples:

```text
04 Aug 2026 03:56 UTC
24-hour freshness window

K8s PGN Staging
Selected cluster

1 of 1 snapshots
Fully committed

No Exceptions
No issues detected
```

## Semantic Treatment

- Latest Collected and Active Scope remain neutral.
- Committed Coverage uses success only when the selected scope is fully committed.
- Partial or missing coverage uses warning or unknown treatment.
- Snapshot Exceptions uses success only when no exceptions exist.
- Stale, missing, partial-collection, or schema exceptions use warning/critical treatment.
- Semantic treatment belongs to the icon and compact status label, not the full metric background.

## Responsive Contract

- Mobile: identity first, then stacked metrics below a horizontal divider.
- Tablet: metrics use a two-column layout without nested cards.
- Wide desktop: identity uses four columns and metrics use eight columns; metrics form one row with subtle vertical dividers.
- Long values truncate visually and remain available through `title` attributes.

## Usage Boundary

Appropriate for:

- Kubernetes Inventory snapshots;
- archived report snapshots;
- worker-materialized governance datasets;
- other read-only datasets with a committed generation boundary.

Do not use it for live provider health, transient request progress, or a general KPI row. Do not repeat its timestamp, freshness, or coverage values in the hero.

## Density Rule

The bar is context, not a dashboard KPI section. Keep it visually compact enough to sit between the hero and the primary catalog without becoming a second hero. Do not add a separate eyebrow row, source card, large metric tiles, progress visualization, or repeated freshness explanation.

## Change Control

When the visual contract changes, update together:

```text
app/templates/components/snapshot_context_bar.html
docs/design/components/SNAPSHOT_CONTEXT_BAR.md
docs/design/patterns/KUBERNETES_INVENTORY_OVERVIEW.md
scripts/verify_snapshot_context_bar_standard.py
tests/contracts/kubernetes/test_inventory_freshness_and_cluster_actions_contract.py
```
