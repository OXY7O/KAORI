# Analytics PDF Publication Audit - 2026-08-04

## Scope

The audit reviewed generated Analytics PDFs for Analytics Overview, Resource Utilization, Capacity Analysis, Storage Analysis, Workload Analysis, Forecast Analysis, Top Consumers, and Alerts & Anomalies.

## Confirmed defects

1. Two publication generations were active. Capacity, Workload, and Top Consumers could fall back to a four-page legacy design when their source was unavailable, while other Analytics reports used the Analytics publication family.
2. Analytics Overview retained an older dense CSS generation and different typography/rhythm.
3. Long Kubernetes identities were placed in narrow columns. The most visible collisions were filesystem/PV/PVC records, active alerts/anomalies, and consumer identities.
4. Resource Utilization displayed raw byte values with a `GiB` suffix instead of converting the values.
5. Forecast and multi-series trend endpoint labels lacked collision resolution.
6. Paragraph spacing and line height were owned by multiple report-specific stylesheets, producing inconsistent rhythm.
7. The public report number exposed an incremental database ID with no family/type convention.

## Remediation

- Established `kaori-analytics-pdf-v3.0` as the only Analytics publication standard.
- Removed the legacy generic PDF template and stylesheet.
- Added a canonical three-page unavailable-source publication.
- Rewrote report-specific stylesheets as specializations only.
- Established one typography scale and vertical-rhythm contract.
- Added concise comparison tables plus complete identity reference registers.
- Added chart label collision resolution with label gutters and leader lines.
- Normalized memory bytes to GiB before presentation.
- Added public report references in the form `KAORI-{FAMILY}-{TYPE}-{YYYYMMDD}-{FINGERPRINT}`.
- Added static verification and render-first visual regression requirements.

## Representative visual validation

The following publication paths were rendered with synthetic stress fixtures:

- Analytics Overview: 12 pages.
- Resource Utilization: 9 pages.
- Capacity Analysis: 9 pages.
- Storage Analysis: 9 pages.
- Workload Analysis: 9 pages.
- Forecast Analysis: 9 pages.
- Top Consumers: 9 pages.
- Alerts & Anomalies: 9 pages.
- Source Unavailable: 3 pages.

The stress fixtures include long namespaces, pod/workload identities, PV/PVC identities, multi-series chart endpoints, and missing-evidence states.

## Reference principles

The implementation follows these external publication principles:

- readable body measure and controlled line height;
- demonstration tables for concise comparisons and reference structures for detail;
- short, explicit column headers and units;
- decluttered charts with light gridlines;
- direct labels only when space allows, otherwise a legend or collision-safe label gutter;
- text remains text rather than being rasterized into chart images.

## Residual validation required in KAORI runtime

After applying the change, generate all eight Analytics report types from the selected cluster in the Dev Container or CI. Inspect the resulting PDFs page by page, because real payload density can exceed the synthetic fixtures. The quality gate prevents known structural regressions, but the release gate remains render-and-review of production-like data.
