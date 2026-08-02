# KAORI Reporting Standard v1

This standard defines shared PDF presentation primitives for KAORI reports.
Analytics Overview is the first system template to adopt the standard.

## Page title contract

- One section number in a 13 mm violet square.
- One-line page title.
- One-line concise description.
- Title copy is optically centered with the number block.
- Long titles use the compact title size; descriptions are shortened in the template rather than wrapped.
- Data cut-off remains right-aligned on the same title grid.

## Metric strip contract

- Metrics use separators rather than cards.
- Standard numeric values use 14 pt.
- Medium values use 11.2 pt.
- Long values use 9.4 pt and may wrap to two lines.
- Long content is never enlarged to fill available space.
- Status is plain semantic text beneath the value.

## Shared files

- `app/templates/reports/pdf/components/_reporting_standard.html`
- `app/static/reports/pdf/reporting_standard.css`

The PDF engine loads the shared stylesheet for all HTML/PDF reports. New or migrated
report templates should import the shared macro file and compose its primitives.

## Typography

- Font family: Inter.
- Page title: 17 pt / 700; compact long title: 15.2 pt / 700.
- Page description: 7.65 pt / 400.
- Metric value: adaptive 14 pt, 11.2 pt, or 9.4 pt.
- Status: 6.75 pt / 600.

## Semantic colors

- Normal: green.
- Warning: amber.
- Critical: red.
- Information: blue.
- Neutral or unavailable: slate.
