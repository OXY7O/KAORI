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
| Cover title | 25.2 pt | 1.05 |
| Page title | 14.6 pt | 1.08 |
| Section heading | 10.2 pt | 1.20 |
| Subheading | 8.2 pt | 1.24 |
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


### 4.2 Family editorial rhythm lock (2026-08-25)

Analytics Overview is no longer allowed to carry a separate typography scale from the other Analytics reports. The shared publication stylesheet owns the effective section heading, helper, body, reference, and paragraph rhythm for the entire Analytics PDF family.

- Section headings use the shared 10.2 pt role.
- Section helper text uses the shared 6.65 pt support role and remains visually distinct from source notes.
- Body narrative remains 8 pt with a 1.44-1.48 line-height range.
- The fixed evidence tables are the smallest readable role; supporting copy and narrative remain larger.
- Section helper descriptions should remain at or below 72 characters. Shorter wording is preferred when a 50/50 layout would otherwise wrap unnecessarily.
- Every major content block follows `title -> description -> content`. A missing description is a publication-contract failure.
- Peer blocks displayed side by side use a symmetric 50/50 layout. If either side becomes too dense, stack the blocks vertically instead of shrinking type or forcing an asymmetric squeeze.
- **Paired-content row alignment:** title, helper description, and content start on shared rows across both peers. The first peer must never inherit top-level section spacing. A 7mm helper slot absorbs one- versus two-line helper copy so the evidence/content baseline remains symmetric.
- Paired sections never add a second clearance layer. The following primary section contributes the single canonical 5.6mm gap; pair wrappers add 0mm bottom padding.
- Dense pages remove or relocate detail before changing the canonical typography or rhythm tokens.
- Report-specific CSS must not own top-level section spacing; `analytics_publication.css` is the single rhythm owner.
- Dense pages compact internal chrome before typography: reduce local table/reference padding, shorten helper copy, or move detail into references before changing font roles.
- Chart labels use stable reference codes for technical or long identities; the complete identity remains in the register below the chart.

The family rhythm is fixed at 1.45 mm from title to description, 3 mm from description to content, 2.2 mm between narrative paragraphs, 3.6 mm from concise register to references, and exactly 5.6 mm between primary sections. Wrapper spacing must never add a second 5.6 mm gap.

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

### 4.3 Deterministic visual-box and footer safety lock (2026-08-25)

Graphic surfaces use fixed publication tokens rather than ad-hoc per-report heights. Paired chart boxes use 50 mm, distribution visual boxes use 48 mm, and wide trend/forecast boxes use 66 mm. SVG content scales inside the locked box; content is never allowed to resize the publication surface unpredictably.

The bottom 18 mm of every content page is reserved as the footer-safe zone. Dense pages must shorten, relocate, or split secondary detail instead of allowing narrative or visual content to cross the footer rule.

Status Language is rendered by the shared publication component in every Analytics report. Report-specific status legend markup is prohibited.

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

## 13. Dynamic content and pagination

Analytics publication layout is content-budgeted. The fixed A4 canvas, canonical typography, and editorial rhythm do not change when evidence becomes longer or more numerous.

- Typography never shrinks to make dynamic content fit.
- Peer information uses 50/50 or stack; report-specific CSS does not own peer column ratios.
- A short balanced pair stays side by side. A dense pair stacks vertically at full width.
- Fixed visual boxes scale chart content inside the box instead of letting the visual grow into adjacent sections.
- Dynamic tables preserve order and may continue on a continuation page with the table header repeated.
- A continuation page belongs to the same section; the next section begins on a new page when the remaining page budget is unsafe.
- Reference registers use two columns only for short, limited identities; long or numerous identities stack to one column.
- Long technical identities remain in reference layers and never force comparison-table columns wider.
- Every page preserves the 18mm footer safety zone.

The reusable density and pagination helpers live in:

```text
app/reports/export/html_pdf/publication_layout.py
```

The shared template primitives expose `adaptive_pair()` and `continuation_heading()` so new report templates can adopt the same behavior without re-implementing spacing or pagination rules.

### Section clearance and reusable content primitives

A section is spaced by publication order, not by HTML element type. The first `<section>` element on a page may appear after a chart, peer pair, metric block, or other `div`; it still receives the canonical **5.6 mm** section gap unless it immediately follows the page title or metric strip. `:first-of-type` must never zero this gap.

Reusable summary cards and chart legends are family-owned primitives. Summary cards use a structured label -> value -> helper layout with a canonical component gap, while chart legends use explicit swatches and spacing. Report-specific CSS may change domain geometry, but must not collapse these primitives into run-on text.
