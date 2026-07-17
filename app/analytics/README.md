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

## Analytics overview Prometheus status flow

- The overview shell validates cluster selection and Prometheus configuration only.
- Live connection health is owned by the dedicated `prometheus-status` lazy section.
- Do not run a separate Prometheus health check before every lazy overview section; this creates contradictory status and unnecessary load.
- A transient failure in one analytics query must be rendered in that section and must not replace unrelated sections with a page-level connection blocker.
- Overview section endpoints are HTMX partial endpoints. Direct browser navigation must redirect to the full Analytics Overview page.
- Keep the inline Prometheus status message concise. Low-level connection exceptions must not be rendered inside the status card.
- A newly observed Prometheus failure emits one operator-facing toast and one Activity Log record per user session and failure fingerprint. Repeated lazy refreshes of the same unresolved failure must not create notification noise.
- Failure feedback uses normalized endpoint, category, and remediation context. The card only directs the operator to the toast or Activity Log for details.
