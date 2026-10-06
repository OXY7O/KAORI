# Kubernetes Service and Ingress Inventory Styling Audit — July 2026

## Decisions implemented

- Applied the Inventory Resource Page Pattern to Service and Ingress Inventory.
- Replaced exposure/TLS scoring with factual network evidence.
- Added compact grouped tables and Adaptive Inline Expanded Detail.
- Added EndpointSlice-first Service backend collection with Endpoints fallback.
- Resolved Ingress backend Service references against committed Service Inventory.
- Made Rows selectors refresh their owning inventory scopes.
- Reused Technical Metadata Collection, Related Resource Collection, Technical Value, Resource Posture Grid, and canonical table/pagination components.

## Shared density corrections

- Evidence grids now render independent bordered tiles and no longer expose empty gray grid cells.
- Metadata collections no longer create nested vertical scrolling in expanded details.
- Node Scheduling & Conditions uses compact evidence tiles and a dedicated taint context row.
- Namespace Access & Security includes explicit control-interpretation context.
- Pod Node Selectors and Tolerations use natural-height peer cards.
- Pod volume Source values use body-size proportional typography, matching adjacent table values.
