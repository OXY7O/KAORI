# KAORI Analytics and Inventory UI Convergence Audit — August 2026

## Scope

This audit compares every Kubernetes Analytics workspace with Kubernetes
Inventory, which is the canonical KAORI interaction and presentation reference.
The audit covers Overview, Utilization, Capacity, Storage, Workload, Forecast,
Top Consumers, and Alerts & Anomalies.

## Problem statement

Analytics had become internally consistent but still felt like a second product:

- `.kaori-analytics-page` replaced the global KAORI Violet-tinted surfaces with
  a gray/slate workspace palette;
- table-like evidence collections owned local shell, filter, row, and pagination
  geometry;
- Inventory and Analytics repeated pagination copy and singular/plural rules;
- unavailable-state payloads could default to 10 rows while Inventory defaults
  to 5;
- filter labels and field associations were inconsistent across domains;
- Capacity review paths used nested bordered boxes instead of the canonical
  KAORI row/action hierarchy.

The result was a visible context switch when moving from Inventory to Analytics,
even though both areas belong to Kubernetes operations.

## Decisions

### Inventory remains canonical

Analytics inherits the same global surface, typography, outline, dark-mode, and
Violet brand tokens as Inventory. The Analytics page marker remains available
for JavaScript and contracts, but no longer creates a second palette.

### Shared data-surface ownership

A filter-independent primitive now owns table/card/filter geometry:

```text
app/templates/components/table_primitives.html
```

`components/table.html` delegates its shared visual macros to that primitive and
retains Kubernetes-specific identity helpers. Analytics shared components import
the primitive directly, avoiding application-filter dependencies in isolated
Jinja rendering.

### Canonical record grammar

Inventory tables and Analytics evidence grids now share:

- outer shell, radius, border, and shadow;
- header surface and typography;
- identity-cell geometry;
- row hover using `bg-kaori-mist`;
- visible filter labels and Violet focus state;
- default rows `5` and options `5/10/25/50`;
- pagination grammar `Showing x–y of z <Resource> · Rows [n]`;
- Previous, numeric page, and Next navigation.

Analytics may retain responsive grid rows when expandable analytical evidence
cannot be represented safely in a conventional table, but it cannot introduce a
different visual system.

### Review-path hierarchy

Capacity Governance Findings and Recommended Review Path now use one bordered
workspace with divider-separated destination rows. Violet represents navigation
and ownership; amber/red/green remain reserved for actual status.

## Files removed or deprecated

No runtime file was removed. The Analytics-specific palette override was removed
from source and compiled CSS. Existing page-specific table and pagination class
ownership is deprecated in favor of the shared primitives.

## Regression protection

The convergence contract verifies:

- no Analytics-specific surface/content/outline token override;
- Inventory and Analytics consume one table primitive;
- one pagination style and singularization owner;
- default page size is 5;
- all Analytics filter labels have explicit field associations;
- Capacity review links use the reusable row pattern;
- table-like Analytics records use Inventory-compatible shell and hover grammar.

Canonical contract:

```text
tests/contracts/analytics/test_analytics_inventory_ui_convergence_contract.py
```

## Validation summary

- Analytics contracts: 252 passed; two pre-existing Intelligence assertions are
  outside this Analytics/Inventory convergence scope.
- Kubernetes contracts: 214 passed.
- Python syntax, internal imports, source hygiene, CSS validation, Jinja parsing,
  and `git diff --check` passed.
- Full Flask application startup was not executed in the audit environment
  because Flask is not installed there; Dev Container startup remains the final
  runtime check.
