# Typography Full Audit — July 2026

## Scope

The audit covered all 348 HTML templates in `app/templates`, including heroes, cards, tables, forms, filters, buttons, labels, modals, drawers, expandable content, empty states, and HTMX partials.

## Baseline findings

- 655 `font-bold` declarations.
- 535 `uppercase` declarations.
- 290 `tracking-wide` declarations.
- 347 uses of `text-[10px]`.
- 333 uses of `text-[11px]`.
- 44 uses of `text-[9px]`.
- Additional one-off 12, 13, 14, 15, 30, and 32 px values.

## Migration applied

- Ordinary `font-bold` declarations were normalized to `font-semibold`.
- Heading, label, legend, and table-head casing utilities were removed; source text now defines casing.
- Arbitrary 9, 11, 12, 13, 14, 15, 30, and 32 px values were mapped to the approved type scale.
- Pure static H1–H6 text was normalized to Title Case while preserving technical and acronym casing.
- The shared 10 px semantic-label exception remains supported.

## Intentional exceptions

Uppercase and tracking remain valid for explicit hero eyebrows and compact category markers. Technical values, resource names, paths, metrics, versions, hashes, commands, URLs, and identifiers retain their authoritative casing.

## Result

The application now has one documented typography scale, consistent semibold title treatment, source-controlled Title Case for content headings, and automated guardrails against reintroducing unsupported arbitrary sizes.
