# Topology Visualization Palette

## Purpose

Kubernetes Topology uses a tokenized five-domain palette rather than assigning an unrelated raw color to every Kubernetes resource type.

All palette values live in `frontend/styles.css`. Templates and JavaScript consume CSS custom properties and semantic classes; they do not contain raw hex values.

## Domain Mapping

| Domain | Resources |
|---|---|
| Scope | Cluster, Namespace |
| Compute | Node, Workload, Pod |
| Networking | Service, Ingress |
| Configuration | ConfigMap, Secret |
| Storage | PersistentVolumeClaim, PersistentVolume |

Resources inside one domain remain distinguishable through a compact resource-type glyph, domain border, and size. Operational health remains a separate status dot using Normal, Warning, Critical, Info, or Unknown.

## External Label Node

Topology nodes use one consistent compact `round-rectangle` badge shape. Avoid diamonds, tags, hexagons, and arrow-like bodies because they make alignment unstable and compete with long Kubernetes identifiers.

The canonical node treatment uses:

- a soft domain fill with a stronger domain border;
- a compact resource-type glyph centered inside the badge;
- a small semantic status dot in the upper-right corner;
- the object name outside and below the badge as one readable line;
- bounded ellipsis for exceptionally long identifiers;
- the complete name and resource type in Resource List, search results, and Details;
- layout calculation that includes the external label to reduce collisions.

Containment relationships use quiet dashed orthogonal lines without arrowheads. Operational/dependency relationships retain colored arrows and only reveal text labels on hover, selection, explicit label mode, or highlighted paths.

## Relationship Tokens

Relationship lines use dedicated visualization tokens for:

- Contains;
- Owns;
- Scheduled on;
- Selects;
- Routes to;
- Uses Configuration;
- Mounts Claim;
- Binds Volume.

Relationship legends use a line swatch and relationship name. They are not operational status labels.

## Rules

- Light and dark values are both defined.
- JavaScript reads tokens using `getComputedStyle`.
- PNG export and mini-map rendering use the same tokens.
- Raw hex values are prohibited in Topology templates and JavaScript.
- New resource types map to an existing domain unless a new domain has a reusable product meaning and is approved first.
