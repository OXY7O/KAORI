# Analytics domain

Analytics converts Prometheus metrics and inventory context into operational
insight. Each analytics workspace is a subdomain under `app/analytics/<workspace>`.

## Source-of-truth rules

- Prometheus and kube-state-metrics are primary for utilization, capacity, request,
  limit, peak, headroom, placement, and overcommit calculations.
- Inventory data supplies identity and snapshot context only.
- Avoid live Kubernetes API fallback in analytics pages.
- Global or "All clusters" views use stored snapshot data; live metric queries
  require a selected cluster.

## Structure

Each workspace normally owns `routes.py`, `service.py`, and optional query or
presentation helpers. Shared metric/query behavior belongs in `base` or `common`.
Do not copy PromQL normalization or dependency-health handling across workspaces.

## UI and query contract

Supported time ranges are `1h`, `6h`, `12h`, `24h`, `7d`, `30d`, and `60d`.
Use one HTMX loading indicator and preserve filter state across pagination/refresh.
Capacity Analysis must retain the agreed Cluster -> Node selector hierarchy.
