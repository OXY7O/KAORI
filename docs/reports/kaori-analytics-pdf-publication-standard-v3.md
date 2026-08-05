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
| Section heading | 10.2 pt | 1.22 |
| Subheading | 8.25 pt | 1.28 |
| Body | 8 pt | 1.46 |
| Lead paragraph | 8.15 pt | 1.50 |
| Table body | 6.8 pt | 1.34 |
| Reference body | 6.9 pt | 1.42 |
| Source note | 6.2 pt | 1.38 |
| Footer | 5.8 pt | 1.0 |

Long narrative text should use a controlled measure rather than spanning the full page width. Paragraph margins are tokenized; browser defaults and per-template paragraph spacing are prohibited.

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
- paragraph spacing is consistent;
- public references use the documented convention;
- source-unavailable output uses the canonical design.
