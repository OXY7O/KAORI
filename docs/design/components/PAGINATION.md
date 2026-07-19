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

## Shared component contract

All new and migrated pagination controls must import:

```jinja
{% import "components/pagination.html" as pagination_ui %}
```

The shared helpers are authoritative:

- `pagination_ui.navigation_classes(disabled=false)` for active Previous and Next controls.
- `pagination_ui.navigation_classes(disabled=true)` for disabled Previous and Next controls.
- `pagination_ui.current_page_classes()` for the active page indicator.
- `pagination_ui.page_size_classes()` for the Rows per page selector.

Page templates may retain their route, HTMX, query-state, and accessibility attributes, but must not create provider- or module-specific visual classes for pagination navigation.

## Previous and Next control contract

Active controls use:

- neutral card background;
- soft neutral border;
- secondary content text;
- Chevron Left or Chevron Right icon;
- `cursor-pointer`;
- Violet-soft hover background;
- Strong Violet hover text;
- Violet focus ring;
- `36px` minimum height;
- `rounded-md` geometry.

Disabled controls use the same geometry and label placement, with:

- muted surface and text;
- `cursor-not-allowed`;
- no hover behavior;
- reduced visual emphasis without disappearing.

Previous and Next are navigation controls. They must never use solid Primary Violet, success, warning, critical, or provider-specific colors.

## Enforcement

Creating local Previous/Next style strings in a new template is not permitted. Extend the shared pagination component when a reusable capability is missing. Route parameters and HTMX state remain owned by the calling template.

## Numeric pagination contract

Numeric pagination is mandatory for standard operational tables. Legacy indicators such as `Page 2 of 8`, `2 / 8`, or a single current-page badge are not permitted after migration.

The control order is:

```text
[Previous] [1] [2] [3] [4] [5] [Next]
```

Rules:

- Show at most five numeric page buttons at one time.
- Preserve the first and last page when the active window is in the middle of a long result set.
- Use a non-interactive ellipsis (`…`) where page ranges are omitted.
- The current page uses Primary Soft, Strong Violet text, a Violet border, and `aria-current="page"`.
- Other numeric pages use the neutral pagination control style and Violet-soft hover treatment.
- Numeric pages are navigation controls and must never use solid Primary Violet.
- Desktop uses numeric buttons. Narrow layouts may collapse to Previous, current page, and Next when required to avoid horizontal overflow.

Window examples:

```text
Page 1 of 20:  [1] [2] [3] [4] … [20]
Page 10 of 20: [1] … [9] [10] [11] … [20]
Page 20 of 20: [1] … [17] [18] [19] [20]
```

The shared macro is authoritative:

```jinja
{{ pagination_ui.numeric_pages(pagination.page, pagination.total_pages) }}
```

The global pagination script derives numeric-page destinations from the existing Previous or Next control. This preserves each template's existing endpoint, query parameters, HTMX target, swap mode, loading indicator, and filter state without duplicating route construction.
