# Empty Registry Pagination — October 2026

**Issue:** [#959](https://github.com/OXY7O/KAORI/issues/959) (bounded child of the existing Design System Lock #572).
**Candidate:** `kaori/review/staging-uat` (local human review; not yet admitted or deployed).
**Authorities:** [PAGINATION.md](../components/PAGINATION.md) and [TABLE_AND_LABEL.md](../components/TABLE_AND_LABEL.md).

## Finding and resolution

A Tenant Access Grant Registry with no rows displayed the canonical empty-state card but no pagination footer. MinIO Integration Coverage, with the same absence of data, correctly displayed `Showing 0–0 of 0 Assets`, Rows, numeric current page, and disabled navigation. The approved standard already mandates that empty operational registries retain the footer. No new visual vocabulary, paginator, data-model contract, or route is necessary.

On the review branch, the specific conditional that hid a pagination footer when `pagination.total_items > 0` was removed from **19 operational template consumers (20 conditions)**:

| Area | Updated consumers |
| --- | --- |
| Kubernetes Tenant | Tenant, Membership, Group, Access Grant, Credential, Namespace Access, Namespace, Resource Profile, and five Operations registries (13 templates) |
| Integrations | Domain Provider/Binding registries (two guards in one template); Kubernetes, MinIO, and Harbor bound-source registries (4 templates) |
| Notification Channels | Channel Registry (1 template) |
| Intelligence | Resolved Alert Operations history (1 template) |

The visible empty-state body and its contextual action remain unchanged, immediately followed by the owning shared pagination footer. Existing filter/Rows parameters, full-page fallbacks, HTMX replacement targets, RBAC, and provider/read-model authority are retained.

## Scope and audit coverage

The Git tree of the reviewed repository contained **862 Jinja HTML templates**. Initial manual source classification examined **160 registry/record/table/history/workspace-style candidate templates** across Access, Integrations, Intelligence, Kubernetes, Platform Operations, reports, Object Storage, and Artifact Registry. Included workspace fragments, table-body partials, and intentionally bounded summary previews were not treated as standalone paginated operational registries. Other reviewed tables with unconditional shared footers were retained unchanged.

A new **repository-wide executable regression contract** (`tests/contracts/design/test_empty_registry_pagination_contract.py`) walks `app/templates/**/*.html` and detects pagination footers nested inside explicit zero-result guards (`*.total_items > 0`). It also protects the 19 remediated consumers and exercises the **shared Jinja registry footer** with a real canonical zero-item pagination window.

This static contract catches the **identified anti-pattern** across the full template tree. It does not by itself prove that every UI table is intended to be paginated or that all dynamic HTMX transitions render correctly; owner-specific tests and Dev Container Visual QA remain required. No new blanket pagination was added to table-free workspaces or to deliberately bounded snapshot previews.

## Accepted empty-state behavior

- Empty table: `Showing 0–0 of 0 {resource}` directly below the empty-state body, inside the same owning table block.
- Rows selector: default 5, options 5/10/25/50, filter scope preserved.
- Navigation: numeric page 1 shown; Previous/Next disabled and non-interactive.
- Non-empty pagination: unchanged server-side filtering and HTMX semantics.
- Missing/stale provider evidence: **not** synthesized as zero; this work only changes whether an existing count's footer is visible.
- Static dashboard previews and bounded summaries remain approved exceptions under the canonical Pagination standard.

## Verification and UAT

**Source review:** confirmed 19 changed operational consumers no longer guard their pagination footer on positive result count, with structurally balanced Jinja `if`/`endif`; tracked exact GitHub diff. The shared Python paginator already clamps zero results to page 1/1 with start/end zero and disabled directions.

**Local checks still required (not executed by the GitHub-only editing environment):**

```bash
python -m pytest -q tests/contracts/design/test_empty_registry_pagination_contract.py
python -m pytest -q tests/contracts/kubernetes/test_tenant_registry_admin_workspace_contract.py
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
```

In Dev Container, use an empty real dataset **and** a filtered-to-zero dataset on Tenant Access Grant Registry, Tenant Registry, Notification Channels, Integration Provider/Binding, Alert Operations resolved history, and bound-source registries. Check matching 0/0 summary, current page 1, disabled Previous/Next, Rows 5/10/25/50, responsive layout, light/dark, and filter reset/HTMX without reload. Repeat on a populated dataset to protect non-empty behavior.

**Acceptance status:** pending local Developer Check and Human Visual QA. No staging admission, deployment, UAT PASS, main promotion, or release is implied by this audit.
