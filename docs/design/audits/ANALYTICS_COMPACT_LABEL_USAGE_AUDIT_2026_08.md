# Analytics Compact Label Usage Audit — August 2026

## Scope

This audit reviews compact label use under `app/templates/analytics` against:

- `docs/design/components/TABLE_AND_LABEL.md`;
- `docs/design/KAORI_STYLING_GUIDE.md`;
- the Inventory label pattern already used by Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration.

The review distinguishes Lucide icon labels from text-only or semantic-dot labels. It does not classify section icon tiles, action-button icons, ranking numbers, chart legends, or ordinary table identity icons as compact labels.

## Canonical Decision

```text
Operational state? → status_label (no Lucide icon)
Repeated operational state needing scan support? → status_indicator_label (semantic dot)
Context/category/type/count? → metadata_label
Context icon adds independent meaning? → metadata_label with icon
Exceptional security/eligibility/high-attention state? → special_label
Ordinary value? → plain text
```

### Labels with a Lucide icon

Use an icon only when it adds independent context that is not already visible nearby:

- active scope or namespace;
- provider/source ownership;
- selected time window or history horizon;
- forecast method;
- storage class or resource type when the row has no existing resource icon;
- external or technical source identity.

### Labels without a Lucide icon

Use text-only metadata or status-dot labels for:

- counts such as `14 Records`, `3 Signals`, `5 Checks`, or `2 Domains`;
- status such as `Ready`, `Warning`, `Critical`, `Limited Evidence`, or `Not Observed`;
- lifecycle such as `Planned`, `Committed`, or `Archived`;
- category names already paired with a section/resource icon;
- repeated status cells in tables and record lists;
- provider names when a provider identity icon is already present in the same record.

## Current Inventory

Static review of the current Analytics templates found:

- 93 `metadata_label(...)` calls across 43 templates;
- 57 metadata labels supplying an icon;
- 119 `status_label(...)` calls across 50 templates;
- only 3 `status_indicator_label(...)` calls across 2 templates;
- 8 page-local compact label candidates outside the canonical shared component.

The large number of icon metadata labels is not automatically incorrect, but several are count/category labels where the icon is decorative rather than informative.

## Confirmed Consistent Areas

The following patterns already align with the standard:

- scope labels using `filter`, `scan-search`, or `globe-2`;
- time-window labels using `clock-3`, `history`, or `calendar-range`;
- source/method labels using `database-zap`, `radio-tower`, or `sigma`;
- storage class and QoS metadata when the label is the only compact type indicator;
- semantic status labels without Lucide icons in Storage, Workload, Forecast, and Top Consumers;
- committed-snapshot posture using a semantic dot in Top Consumers.

## Inconsistencies Requiring Analytics Follow-up

### P0 — Page-local compact labels

Replace manual compact label markup with the canonical shared component in:

```text
app/templates/analytics/kubernetes/overview/partials/_top_consumers_snapshot.html
app/templates/analytics/kubernetes/top_consumers/partials/_summary.html
```

Current issues:

- category/count labels manually add borders;
- arbitrary `text-[10px]` and `text-[11px]` sizes are used;
- category labels duplicate the nearby category title/icon;
- count labels use a heavier treatment than necessary.

Target:

- category/count metadata uses `table_label.metadata_label(..., size='compact')` without an icon;
- risk remains `status_label(...)` or `status_indicator_label(...)`;
- ordinary eyebrow text remains plain text, not a compact label.

### P1 — Decorative icons on count metadata

Remove icons from count-only metadata unless the count represents a distinct external source or scope. Priority templates:

```text
app/templates/analytics/kubernetes/overview/partials/_top_consumers_snapshot.html
app/templates/analytics/kubernetes/overview/partials/_workload_snapshot.html
app/templates/analytics/kubernetes/overview/partials/_alerts_snapshot.html
app/templates/analytics/kubernetes/overview/partials/_forecast_snapshot.html
app/templates/analytics/kubernetes/overview/partials/_recommendations.html
app/templates/analytics/kubernetes/alerts/partials/_ownership_summary.html
app/templates/analytics/kubernetes/alerts/partials/_incident_readiness.html
app/templates/analytics/kubernetes/capacity/partials/_risk.html
app/templates/analytics/kubernetes/workload/partials/_tenant_quota_section.html
```

Examples that should normally be iconless:

```text
16 Ranked Records
6 Health Signals
3 Candidates
5 Checks
4 Groups
2 Quota Objects
```

### P1 — Repeated table states should use semantic dots

Dense record lists should prefer `status_indicator_label(...)` for repeated operational states. Review:

```text
app/templates/analytics/kubernetes/alerts/partials/_alerts_table_row.html
app/templates/analytics/kubernetes/alerts/partials/_anomalies_table_row.html
app/templates/analytics/kubernetes/workload/partials/_workload_mapping_section.html
app/templates/analytics/kubernetes/workload/partials/_tenant_quota_section.html
app/templates/analytics/kubernetes/storage/partials/_filesystem_panel.html
app/templates/analytics/kubernetes/storage/partials/_persistent_volume_claims_panel.html
app/templates/analytics/kubernetes/storage/partials/_persistent_volumes_panel.html
app/templates/analytics/kubernetes/top_consumers/partials/_consumer_detail_results.html
```

Use dots only where they improve scanning. Risk/severity labels that are already visually distinct and not repeated in a dense status column may remain text-first.

### P1 — Context icons duplicated by an existing identity icon

Remove the icon from metadata when the same concept is already represented by the row/card identity icon. Review:

```text
app/templates/analytics/kubernetes/top_consumers/partials/_consumer_detail_results.html
app/templates/analytics/kubernetes/workload/partials/_workload_mapping_section.html
app/templates/analytics/kubernetes/workload/partials/_tenant_quota_section.html
```

Examples include resource/category labels directly beside a resource icon or repeated QoS/provider labels in the same identity group.

### P2 — Technical matcher and key/value tokens

Matcher and label-pair tokens in Alert Intelligence are metadata, not health status:

```text
app/templates/analytics/kubernetes/alerts/partials/_alerts_table_row.html
app/templates/analytics/kubernetes/alerts/partials/_silence_inhibition_summary.html
app/templates/analytics/kubernetes/alerts/partials/_routing_summary.html
```

They should remain iconless. Use either canonical metadata labels or plain compact technical tokens based on density; do not add semantic status icons.

## Implementation Sequence

1. Normalize manual labels and arbitrary compact typography in Top Consumers.
2. Remove decorative icons from count-only Analytics labels.
3. Convert repeated status columns to semantic-dot labels where scanning improves.
4. Remove duplicated context icons from rows that already have an identity icon.
5. Add contract tests that reject page-local compact label class bundles and status labels with decorative Lucide icons.

## Reference Implementation

Integration Overview is normalized first in the accompanying patch:

- runtime scope metadata uses an icon because it conveys context;
- runtime target count is iconless;
- provider lifecycle/readiness uses semantic-dot or text-only labels;
- repeated runtime table statuses use semantic-dot labels;
- provider names and planned counts use iconless metadata labels;
- no page-local bordered compact labels are introduced.


## Final Refinement Resolution — 2026-08-07

The outstanding compact-label follow-up is now implemented across the complete Kubernetes Analytics template tree.

Final measured state:

- 95 `metadata_label(...)` calls;
- 111 `status_label(...)` calls;
- 11 `status_indicator_label(...)` calls;
- 0 page-local compact label bundles using `inline-flex + min-h-6 + rounded-md`;
- 0 Analytics `status_label(...)` calls supplying a decorative Lucide icon;
- count-only metadata is iconless;
- dense repeated state columns use semantic-dot labels where scanning benefits.

Capacity Analysis was the visible regression that triggered the final pass. The Resource Envelope pressure rows previously passed a semantic Lucide icon into `status_label(...)`, while other Capacity labels were text-first. That is now normalized: the compact status remains iconless, while the separate Operational Reading icon tile may remain semantic because it is not a compact label.

The final pass also resolves the previously documented P0/P1/P2 items:

- Top Consumer page-local compact badges are replaced by the canonical shared label component or removed when redundant with the resource title/icon;
- decorative icons are removed from count-only labels in Overview, Capacity, Workload, Forecast, Storage, Utilization, and Alerts & Anomalies;
- Alert state, Workload configuration/evidence state, Tenant quota state, and PV/PVC lifecycle state use `status_indicator_label(...)` in dense record rows;
- duplicated resource/QoS context icons are removed where the row identity already carries the resource glyph;
- Alertmanager matcher, grouping-key, and equal-label technical tokens remain iconless metadata.

Regression guard:

```bash
python scripts/verify_analytics_compact_label_standard.py
```

The verifier is part of `scripts/quality_gate.sh` and rejects:

- Lucide icons passed to ordinary Analytics `status_label(...)` calls;
- decorative icons on count-only metadata;
- page-local compact label markup;
- arbitrary 10/11 px compact-label typography in Analytics templates;
- loss of the canonical semantic-dot pattern on dense repeated state columns.
