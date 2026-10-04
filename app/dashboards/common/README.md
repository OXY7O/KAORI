# Operational Dashboard Common Boundary

This package contains only domain-neutral application contracts that have been proven by at least two Operational Dashboard consumers.

Current owner:

- `operational.py` — canonical tab order/fallback, canonical pagination facade, and HTMX request detection.

Keep permissions, readiness, routes, services, schemas, repositories, provider clients, and domain evidence in their owning capability. Do not add a generic dashboard route factory or service base class without a separately approved architecture change backed by multiple stable consumers.
