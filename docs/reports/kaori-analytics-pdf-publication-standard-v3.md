# KAORI Analytics PDF Publication Standard v3.0

**Status:** Mandatory canonical publication contract
**Owner:** KAORI Reports
**Applies to:** Every Analytics PDF artifact
**Canonical renderer:** WeasyPrint HTML/PDF

## 1. Scope

This standard owns the publication design and rendering behavior for:

- Analytics Overview (`AOV`)
- Resource Utilization (`RUT`)
- Capacity Analysis (`CAP`)
- Storage Analysis (`STO`)
- Workload Analysis (`WLA`)
- Forecast Analysis (`FCT`)
- Top Consumers (`TPC`)
- Alerts & Anomalies (`ALA`)
- Analytics source-unavailable publications


Canonical contract identifier: `kaori-analytics-pdf-v3.0`. Chart labels use a collision-safe gutter when direct placement is not safe.

Every Analytics PDF uses the shared template and stylesheet below:

```text
app/templates/reports/pdf/components/analytics_publication.html
app/static/reports/pdf/analytics_publication.css
```

Report-specific styles may specialize chart geometry, page budgets, and evidence-specific layouts. They may not redefine global page geometry, typography, paragraph rhythm, tables, cover, header, or footer.

## 2. Publication identity

The database primary key is internal. The document reference shown in the PDF, filename, and storage object uses:

```text
KAORI-{FAMILY}-{TYPE}-{YYYYMMDD}-{FINGERPRINT}
```

Example:

```text
KAORI-ANL-STO-20260804-A008D2C2
```

The reference is generated centrally by `app/reports/reference.py`. Numeric incremental IDs must not be exposed as the public document number.

## 3. Page and layout contract

- Paper: A4 portrait.
- One evidence section per fixed page.
- Page header, title row, content boundary, and footer are identical across Analytics report types.
- Footer area is reserved; content may not enter it.
- Section separators are omitted. Hierarchy is created with spacing, typography, and surface changes.
- Every page must render without clipping, collision, orphan labels, or text outside its content boundary.

## 4. Typography

Canonical family:

```css
"Inter Analytics", "DejaVu Sans", Arial, sans-serif
```

| Role | Size | Line height |
|---|---:|---:|
| Cover title | 26.5 pt | 1.04 |
| Page title | 15 pt | 1.08 |
| Section heading | 10 pt | 1.20 |
| Subheading | 8.25 pt | 1.25 |
| Body | 8 pt | 1.44 |
| Lead paragraph | 8.15 pt | 1.50 |
| Table body | 7 pt | 1.36 |
| Reference body | 6.95 pt | 1.44 |
| Source note | 6.35 pt | 1.42 |
| Footer | 5.8 pt | 1.0 |

Long narrative text should use a controlled measure rather than spanning the full page width. Paragraph margins are tokenized; browser defaults and per-template paragraph spacing are prohibited.


### 4.1 Precision-layout refinement (2026-08-21)

The v3.0 contract is refined with the following mandatory publication rules. This is not a new visual family; it tightens the existing standard based on production report review.

- Prefer one-line values, dates, statuses, units, thresholds, and short labels in fixed comparison registers.
- Preserve readable type size. If content does not fit, shorten presentation copy or move the full detail to a reference register instead of shrinking typography.
- Technical identities receive horizontal space before wrapping. Full identities belong in a full-width reference register when a narrow table would force repeated line breaks.
- Publication labels must identify the actual measurement boundary. Node-filesystem utilization, PVC observed capacity, PVC requested capacity, and bucket/system capacity are separate evidence domains and must never share an ambiguous `Storage` label when their denominators differ.
- A current value, projected value, and headroom value presented on one row must use the same evidence series and denominator.
- Forecast rows must take both current and projected values from the committed forecast series when that series is available. A current value from another analytics card must not be substituted into a forecast row.
- Generated timestamps in fixed registers use a human-readable UTC format. Raw ISO timestamps with microseconds are prohibited in publication tables.
- Source registers may use compact publication labels such as `Metrics Cache`, `Kubernetes Inventory`, `Analytics Snapshots`, and `Alert Cache`; the full source identity remains available elsewhere in the evidence boundary.
- Normalize non-breaking and renderer-sensitive dash characters before publication so identifiers and `cut-off` language do not produce broken glyphs.


### 4.2 Analytics Overview management typography profile (2026-08-21)

Analytics Overview is the management-facing member of the Analytics publication family. Typography follows a compact A4 publication scale: fixed evidence tables are the smallest readable role, then supporting copy, body narrative, subsection headings, and page headings scale upward in a stable hierarchy.

| Role | Analytics Overview target |
|---|---:|
| Page title | 17.5 pt |
| Section heading | 14 pt |
| Subheading / register heading | 10-11 pt |
| Primary narrative content | 12 pt |
| Section helper text | 9 pt |
| Fixed comparison table | 8-8.5 pt |
| Reference/detail body | 8-9 pt |
| Source note | 8 pt |

Fixed evidence tables intentionally own the smallest readable type so scalar fields can remain on one line inside the A4 content frame. Narrative text must remain visibly larger than tables, and headings must step upward consistently. Tables may never expand beyond the report content margin to preserve a larger font. Short publication labels and reference registers are preferred instead.

Every major register or evidence block should have a one-sentence helper description when the heading alone does not explain the reading purpose. Full-width guidance should use the full content measure rather than an arbitrary narrow paragraph width.

### 4.3 Management readability and canvas safety (2026-08-24)

Production Analytics PDFs must be readable by technical operators and management without requiring the reader to decode dense inventory structures. Analytics Overview is the visual reference for content hierarchy, spacing, concise registers, reference legends, and management interpretation.

- Major content blocks require approximately one to one-and-a-half paragraph of visual separation. Internal label-to-value spacing may remain tighter, but adjacent primary sections must never look attached.
- Every page follows a visible hierarchy: page heading, one-line purpose, summary metrics when useful, primary evidence block, concise comparison register, reference/detail block, and management interpretation or decision.
- Start from the canonical type scale. When a page is dense, reduce data volume or move detail into a reference block before reducing font size. The smallest table role remains the documented minimum.
- Fixed comparison tables should keep scalar values, short statuses, dates, and reference codes on one line whenever practical. Long technical identities and explanations move to a stable reference code and a separate reference register.
- No table, chart, legend, label, or narrative may exceed the A4 content frame or reserved footer boundary. Content must be rearranged, split, summarized, or reduced before it is allowed to cross the canvas margin.
- Multi-series charts reserve a dedicated right-side label gutter. Endpoint labels are anchored inside that gutter and may use leader lines; they never overlap plotted data or extend beyond the SVG view box.
- If a table would become an inventory dump, the analytics report is a management and operational summary: retain only the decision-relevant top rows and aggregate posture. The inventory publication owns exhaustive object-level detail.
- Charts, labels, registers, reference notes, and management conclusions must remain visually separate. A chart legend may replace repeated long labels when that improves the reading path.

## 5. Vertical rhythm

| Relationship | Canonical space |
|---|---:|
| Page title to first content | 5 mm |
| Section to section | 5.6 mm |
| Heading to subtitle | 1.45 mm |
| Subtitle to content | 3 mm |
| Paragraph to paragraph | 2.2 mm |
| Concise register to references | 3.6 mm |

Report-specific templates may reduce page density by removing content or moving detail into references. They may not compress typography or randomize margins to force content into a page.

## 6. Table and dynamic text policy

Tables are for comparable fixed decision fields. Technical identities and long narrative descriptions are dynamic evidence and must not be forced into narrow columns.

Canonical pattern:

```text
Concise register
  Ref. | Status | Scalar value | Owner | Date

Reference register
  Ref. → complete technical identity and supporting metadata
```

Rules:

- Use stable reference codes such as `M1`, `C2`, `PV3`, or `A4`.
- Preserve complete identities in a reference register below the comparison table.
- Never use ellipsis for evidence.
- Never use `word-break: break-all`.
- Use normal word wrapping and explicit overflow-safe cells.
- Keep column headers short and include units in the header or title.
- Prefer a dedicated column over a second line inside a cell when a scalar such as threshold ETA can remain one line.
- A fixed register should not mix two denominators under one resource label.
- Avoid merged cells.
- Do not split one row across pages.
- Missing evidence remains `Not Available`, `Not Collected`, `Partial Coverage`, or `Source Unavailable`; it is never converted to zero.

## 7. Chart policy

Charts must remain subordinate to the report narrative and must not overlap labels, axes, thresholds, or neighboring content.

- Use light gridlines and no decorative shadow or 3D treatment.
- Use concise chart titles and separate subtitles.
- Technical identities use reference codes in charts.
- Multi-series endpoints use a dedicated label gutter.
- Labels have a minimum vertical gap and leader lines when displaced.
- The data anchor is never moved to solve a label collision.
- A concise register or reference register must preserve the values and identities shown in the chart.
- Missing observations remain gaps.

Collision handling is centralized in:

```text
app/reports/export/html_pdf/chart_labels.py
```

## 8. Source-unavailable publication

Unavailable Analytics sources use the same publication family. The canonical output is three pages:

1. Cover and selected reporting boundary.
2. Source Availability and explicit evidence limitation.
3. Recovery and Generation Controls.

The renderer must not fall back to a legacy generic report design. Selected cluster, namespace, period, and cut-off remain visible. No operational posture may be inferred from unavailable evidence.

## 9. Source and renderer boundary

- Exactly one selected cluster is required.
- Collectors run before rendering.
- HTML templates and WeasyPrint do not query Kubernetes, Prometheus, Alertmanager, S3, or another provider.
- Analytics CSV and PDF use the same report-specific collector source.
- Public reference and scope are shared by the artifact, filename, storage object, and user-visible generation result.

## 10. Prohibited patterns

- Legacy `report.html` or `report.css` fallback.
- Numeric public `Report ID`.
- Per-report global typography overrides.
- Arbitrary paragraph margins.
- Text smaller than the canonical minimum to make a page fit.
- Full technical identities inside chart labels.
- Long descriptions inside fixed comparison tables.
- `text-overflow: ellipsis` for evidence.
- Converting missing data to zero.
- Labels drawn directly over plotted data without collision handling.

## 11. Quality gate

Run:

```bash
python3 scripts/verify_analytics_pdf_publication.py
python3 scripts/verify_single_pdf_engine.py
python3 scripts/verify_report_generation_contract.py
```

The verifier checks publication registry coverage, typography, paragraph rhythm, table/reference patterns, chart collision handling, public reference convention, legacy path removal, source-unavailable behavior, and documentation synchronization.

## 12. Review checklist

Before release, render every Analytics report and inspect every page as an image. Confirm:

- all pages are A4 and the expected count;
- header/title/footer alignment is identical;
- no clipping, overlap, black square, broken glyph, or text spill;
- tables contain concise comparable fields;
- complete identities exist in references;
- charts have readable labels and visible gaps for missing observations;
- current, projection, capacity, and headroom values use the documented evidence denominator;
- fixed-table timestamps, statuses, and scalar values remain on one line where practical;
- paragraph spacing is consistent;
- public references use the documented convention;
- source-unavailable output uses the canonical design.
