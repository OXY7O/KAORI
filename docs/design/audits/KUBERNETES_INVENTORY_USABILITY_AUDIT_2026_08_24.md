# Kubernetes Inventory Usability Audit — 2026-08-24

## Scope

Reviewed Inventory Overview, Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, Configuration, shared Full Workspace Modal primitives, compact filter rows, and committed-snapshot read boundaries.

## Result

**Aligned with the KAORI Inventory Resource Page pattern after the 2026-08-24 usability refinement.**

### Visual system

- Palette remains semantic-token driven (`bg-surface-*`, `text-content-*`, `border-outline-*`, KAORI Violet identity tokens, and semantic status tokens). No page-local hex palette was introduced.
- Detail typography keeps the existing hierarchy: resource title `text-xl`, section title `text-sm font-semibold`, evidence labels/value body `text-sm`, and supporting context `text-xs`.
- The resource-sheet description rail now follows a shared 1:3 grid. The 25% rail aligns with one cell of the four-column summary strip, removing the previous fixed-width asymmetry across large modals.
- Embedded metadata and related-resource bands reuse the same grid primitive, preventing alignment drift between resource families.

### Interaction and accessibility

- Kubernetes UID/UID, System UUID, and concrete IP evidence use one shared icon-only copy action backed by the global `clipboard.js` behavior.
- Copy buttons retain keyboard focus treatment, accessible `aria-label`, title text, and a copied-state icon/label. Unavailable values do not expose a misleading copy action.
- Ingress DNS access uses `target="_blank"` plus `rel="noopener noreferrer"`. Wildcard DNS declarations remain reference-only.
- Search labels for dense Pod, Ingress, Storage, and Configuration filters are shortened to `Search`; placeholders retain enough context to explain searchable fields.

### Content and semantics

- Namespace governance wording is shorter without changing the evidence boundary: absent namespace controls remain neutral until a policy evaluates them, and KAORI does not infer cluster-level PSA defaults from missing labels.
- Reported Quotas remain factual inventory evidence. The redesign uses one bordered quota box with a clear Resource / Hard Limit comparison instead of a loose two-column value wall.
- Ingress direct-open actions are convenience navigation only. They do not assert DNS resolution, reachability, TLS validity, or application health.
- All detail pages continue to read committed inventory snapshots; no live Kubernetes API call was added.

### Code ownership

- Modal geometry and copy interactions are owned by `components/details/_detail_content.html`.
- Embedded metadata/relationship bands consume the shared geometry rather than duplicate it.
- Ingress URL derivation is owned by the Ingress presentation service, not by ad-hoc template string construction.
- Resource templates only opt into shared capabilities (`copyable=true`) or render presentation data.

## Release checks

The permanent contract covers shared 1:3 alignment, copy actions, namespace quota presentation, compact search copy, Ingress DNS actions, and semantic-token usage. Existing Inventory final-lock and per-resource verifier suites remain the release authority for committed-snapshot, authorization, pagination, and resource-specific behavior.
