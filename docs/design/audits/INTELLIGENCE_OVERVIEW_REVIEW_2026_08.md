# Intelligence Overview Review — 2026-08

## Decision

Create a dedicated **Intelligence Overview** at `/intelligence/` and make it the entry point for the Intelligence category. Recommendations remains a separate workspace rather than acting as the category root.

## Product role

The Overview is a cross-domain navigation and posture surface. It summarizes four existing capability owners without collapsing their responsibilities:

1. **Recommendations** — catalog-backed findings from committed KAORI evidence.
2. **Alert Intelligence** — provider alert context resolved on demand for a selected managed asset.
3. **Rule Catalog** — canonical definitions for detection ownership, evidence boundaries, provider coverage, severity, and operator response.
4. **Automation Control** — system runbooks, decisions, approvals, readiness, controlled execution, verification, and recovery.

## Data boundary

The Overview must remain provider-free. It may read committed inventory-backed recommendations, registered asset counts, Rule Catalog definitions, and persisted Automation Control posture. It must not query Prometheus, Alertmanager, MinIO, Kubernetes, or another infrastructure provider merely because the category landing page is opened.

Alert retrieval remains owned by Alert Intelligence. Infrastructure mutation remains owned by Automation Control.

## Layout

The page uses the canonical KAORI Hero and Intelligence workspace components:

- Hero with current Intelligence posture;
- four capability cards;
- Current Priorities from active recommendation findings;
- Evidence & Control Boundaries explaining ownership.

The page intentionally avoids charts, provider-health duplication, or an alternate alert table.

## Navigation

- Sidebar order: Overview, Recommendations, Alert Intelligence, Rule Catalog, Automation Control.
- Welcome Intelligence card opens Overview.
- Breadcrumb ownership includes `intelligence.*`, `alert_intelligence.*`, and `automation_control.*`.

## Release contract

`tests/contracts/intelligence/test_intelligence_overview_contract.py` and `scripts/verify_intelligence_baseline_lock.py` prevent regression back to a redirect-only root or provider-coupled Overview.
