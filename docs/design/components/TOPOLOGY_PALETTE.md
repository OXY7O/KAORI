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

Containment relationships use quiet dashed orthogonal lines without arrowheads. Operational/dependency relationships retain colored arrows. Relationship labels stay hidden by default at every graph size to avoid colliding with resource names. Hovering one edge reveals only that relationship label and highlights that edge; an explicitly selected edge retains its label, while the existing path-highlight mode and Always Show Relationship Labels control may reveal additional labels intentionally. The existing Relationship Visibility controls double as the tokenized relationship legend, explaining dashed scope containment versus solid operational dependencies. Edge labels use a compact horizontal, tokenized background. Visible `contains` labels sit below the dashed elbow connector, in the open relationship corridor rather than directly on external resource names; the same clearance applies to hover, selected edges, highlighted paths, and the explicit always-show mode.

## Readable Label and Operational Edge Hierarchy

- External **resource names** use regular Inter 400 (including Cluster), while compact **CL/NS/ND/WL/PD** glyphs remain bold inside each badge. This preserves hierarchy without bolding long Kubernetes identifiers.
- Edge relationship chips use medium Inter 500; relationship text remains hover/selection/explicit-toggle only, and containment chip clearance is unchanged.
- Containment lines remain quiet dashed lines without arrowheads. Operational arrows preserve the direction of committed source-to-target evidence: `owns` (Workload → Pod) and `scheduled_on` (Pod → Node). They must not be restyled to look like containment, nor should arrows be removed to hide the relationship.
- Default operational lines use restrained widths/opacity and smaller arrowheads (scheduled placement is less prominent than ownership); hovering, explicit path focus and selection retain their existing emphasis. Reuse the current Violet/semantic relationship tokens in both themes, including the Controls legend.

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
