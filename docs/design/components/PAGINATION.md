# KAORI Pagination Component Standard

## Purpose

Pagination keeps operational tables bounded, stable, and understandable while preserving the active filter context. This contract applies to every paginated table or list unless a module specification explicitly documents an approved exception.

## Data contract

- Default page size: `5`.
- Allowed page sizes: `5`, `10`, `25`, and `50`.
- Changing page size returns the result to page `1`.
- Operational datasets use server-side pagination by default.
- A paginated HTMX request preserves search, filters, sorting, selected cluster, selected namespace, time range, and page size.
- `Show all` is not permitted for operational tables.

## Summary format

Every pagination footer must identify the resource being counted:

```text
Showing {start}–{end} of {total} {resource}
```

Examples:

```text
Showing 1–5 of 27 pods
Showing 1–1 of 1 user
Showing 0–0 of 0 integration targets
```

Rules:

1. Use the table resource name, not the module name.
2. Use an en dash (`–`) between the start and end values.
3. Use singular or plural wording appropriate to the total.
4. Empty results remain explicit as `Showing 0–0 of 0 {resource}` so the footer does not disappear or shift.
5. Resource labels use sentence-style lowercase unless the resource contains an official proper name or acronym, such as `TLS secrets`.

## Footer layout

Desktop order:

```text
Showing 1–5 of 27 pods    Rows per page [5 ▼]    [Previous] [1] [2] [3] [Next]
```

The footer belongs inside the table surface and uses a top border. It contains three logical groups:

1. Result summary.
2. A visible `Rows per page` label and selector.
3. Previous, numeric page controls, and Next.

On narrow screens, groups may wrap. The resource summary and page-size selector must remain available. Numeric page controls may be compacted, but Previous and Next remain accessible.

## Visual contract

- Pagination controls use the shared secondary-control geometry.
- Control minimum height: `36px`.
- Radius: `rounded-md` or the current global control radius until the radius migration is complete.
- Active page: Primary Soft background with Strong Violet text and a visible Violet border.
- Disabled Previous/Next: muted surface, muted text, `cursor-not-allowed`, and no active hover treatment.
- Page-size selector: neutral surface, soft border, and Violet focus ring.

## Interaction contract

- Previous is disabled on the first page.
- Next is disabled on the final page.
- Invalid page values are normalized to the nearest valid page.
- Invalid page-size values fall back to `5`.
- HTMX pagination updates only the owning table region and must not reload the full page when that page already uses HTMX.
- The browser URL should preserve pagination state when the page workflow already uses `hx-push-url`.

## Accessibility

- The page-size selector has a visible `Rows per page` label; `aria-label` may supplement but not replace it on standard table footers.
- The current page is exposed with `aria-current="page"` when numeric controls are used.
- Icon-only compact pagination controls require an accessible label.
- Disabled controls must be semantically disabled where a button is used, or removed from the tab order where a link fallback is unavoidable.

## Approved exceptions

Static dashboard snapshots and intentionally bounded preview lists may omit the page-size selector. Their limits must be documented in the owning module and they must not masquerade as a full operational registry.
