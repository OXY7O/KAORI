# Intelligence Recommendations Final Recheck — 2026-08

## Decision

Recommendations remains the cross-domain, committed-evidence finding workspace for Kubernetes and Object Storage. The page does not become a provider dashboard or an execution surface.

## Reviewed Boundaries

- The route remains protected by `intelligence.view`.
- Recommendation findings are rebuilt from committed KAORI inventory/analytics evidence and canonical Intelligence rules.
- No direct Prometheus, Alertmanager, Kubernetes, MinIO, or S3 query is introduced by the Recommendations page.
- Detail review remains a side-drawer workflow; records do not expand inline.
- Live-state validation and remediation are described as workflow gates, not performed from the recommendation table.
- Automation Control remains the owner of governed execution.
- Filters and pagination replace only the results region except Reset, which restores the complete workspace controls.
- Default pagination remains 5 with 5/10/25/50 options.

## UI Recheck

The filter surface is reduced to two desktop rows for faster scanning:

1. Search / Domain / Provider Coverage / Signal Source.
2. Severity / Category / Resource Type / Rule Type.

A standalone **Recommendation Summary** section is rendered between the Hero and Recommendation Workspace. It reports matching findings, Kubernetes and Object Storage finding counts, critical/warning priority counts, active-filter state, and the committed-evidence boundary. The Summary remains filter-aware through HTMX out-of-band refreshes while the Recommendation Workspace continues to own filters, records, and pagination. Counts represent all matching findings, not only the current page.

## Result

No page redesign is required. The existing Hero, recommendation table/cards, pagination, and side-drawer detail system remain valid. The audit change is limited to filter density, a standalone filter-aware cross-domain Recommendation Summary, browser form-state hardening, and regression contracts around the evidence and execution boundaries.
