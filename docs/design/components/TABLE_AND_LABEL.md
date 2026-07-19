# KAORI Table, Data Block, and Compact Label Standard

This document is the authoritative contract for operational tables, data-block headers, filters, row content, labels, actions, loading indicators, empty states, and table pagination across KAORI.

## 1. Information hierarchy

A complete table block follows this order:

1. Block header: icon, title, short description, optional actions.
2. Loading bar, when the region has an asynchronous operation.
3. Filter bar.
4. Table header and rows.
5. Empty or compact error state, when applicable.
6. Pagination footer.

The hero and page shell are not part of the table block. An HTMX refresh must replace only the relevant data region and must not move the hero or block header.

## 2. Shared component

`app/templates/components/table.html` owns the standard visual classes and reusable title-cell markup. New tables must import this component rather than inventing page-local visual styles.

The shared component provides:

- block and block-header classes;
- loading-bar classes;
- filter label/input/select classes;
- table, header, row, and cell classes;
- title/resource cell markup;
- compact table-action classes.

Page templates still own endpoint selection, authorization, data, filters, sorting, HTMX state, and domain-specific content.

## 3. Table block header

Use an icon, Title Case title, and a short description.

- Icon: 18–20 px inside a consistent 40 px Violet-soft container.
- Title: 16 px, semibold, primary content color.
- Description: 14 px, muted/secondary, normally one line and never more than two.
- Header actions: right aligned on desktop and wrapped below the title on narrow screens.
- Maximum visible header actions: two.

## 4. Loading bar

When a page or table region uses a loading bar, place it immediately below the block header and before filters or table content.

- Full width of the table block.
- 2–4 px high.
- Violet progress indicator over a Violet-soft track.
- Must not float over content or be attached to a toast.
- Must not change block geometry when shown.
- The associated region uses `aria-busy` where practical.

A form-local progress indicator may remain inside a form action area when it only represents that form, but table refresh, polling, validation, and synchronization indicators follow this block-level placement.

## 5. Column alignment

- Every table header and cell is left aligned by default.
- The rightmost action column is right aligned in both its `<th>` and `<td>` cells.
- Ordinary status, numeric, timestamp, and operational cells are not centered merely for decoration.
- A documented analytics table may use numeric alignment when comparison accuracy requires it.
- All body cells use vertical alignment `middle`.

## 6. Table header typography

Column labels use:

- Title Case text;
- 11–12 px;
- semibold;
- secondary/muted content color;
- normal letter spacing;
- no global uppercase transformation.

Headers render exactly once. A table partial updated through HTMX must not duplicate the table header.

## 7. Resource/title column

The principal resource column uses either:

- primary text only; or
- meaningful icon + primary text + one optional supporting line.

Primary text:

- 14 px semibold;
- main content color;
- one line with truncation and a `title` value for long content.

Supporting text:

- 12 px muted;
- one line;
- suitable for cluster, namespace, provider, type, email, or stable secondary identity.

Icons are 16–18 px and must carry meaning. Do not add an icon to every cell or use decorative icons that do not improve interpretation.

## 8. Row data

Two patterns are permitted:

- text-only for direct values;
- icon + text when the icon adds operational meaning.

Use one pattern consistently within a column. Technical detail that would make the row dense belongs in an expandable row, drawer, modal, or detail page.

Rows use a soft divider and a very subtle Violet-mist hover. Do not apply a shadow to each row.

## 9. Compact labels

`app/templates/components/table_label.html` remains authoritative for status and metadata labels.

Geometry:

- minimum height: 24 px;
- horizontal padding: 8 px;
- vertical padding: 2–4 px;
- text: 10 px semibold;
- icon: 12 px;
- gap: 4–6 px;
- radius: `rounded-md`;
- never `rounded-full`.

Status labels use the global semantic palette. Metadata labels use Violet or neutral context styling. Timestamps stay plain text.

Labels remain brief, such as `Ready`, `Degraded`, `Pending`, `Not Observed`, or `Disabled`. Longer evidence belongs outside the label.

## 10. Table actions

Table actions are compact navigation or utility controls, not page-level mutation buttons.

Standard:

- icon + text when space permits;
- visible label maximum: two words;
- height: 32–36 px;
- `rounded-md`;
- icon: 14–16 px;
- text: 12–13 px medium;
- white/card background and soft border;
- Violet-soft background and Strong Violet text on hover;
- visible Violet focus ring;
- pointer cursor when active and not-allowed cursor when disabled.

Examples: `Open`, `View Details`, `Edit`, `Retry Sync`, `Run Now`, `Approve`, `Deny`, and `Archive`.

A destructive action uses the same geometry and differs through Critical semantic color and its icon. Show at most two row actions. Put additional actions in a `More` menu. Icon-only controls require both `title` and `aria-label`.

## 11. Filter bar

On desktop, filters share one row when space allows. On smaller screens, use a responsive grid or stack without horizontal overflow.

Filter labels:

- Title Case;
- 12 px semibold;
- secondary content color;
- positioned above the field.

Inputs and selects:

- height: 40 px;
- `rounded-md`;
- soft border and card background;
- 14 px text;
- stronger border on hover;
- Violet border and focus ring on focus;
- pointer cursor for selects and filter buttons;
- muted, not-allowed disabled state.

Search placeholders are resource-specific, such as `Search Pods` or `Search Integration Targets`. A filter or search change resets the table to page 1 and preserves all other relevant state.

## 12. Sorting

Sortable headers show a 12–14 px sort indicator, use Strong Violet for the active sort, expose `aria-sort`, and preserve sort state across filter and pagination requests. The action column is never sortable.

## 13. Empty and error states

Empty and compact error states remain inside the table surface and below the filter/context area.

- Keep the table context and pagination footer stable.
- Empty pagination summary remains `Showing 0–0 of 0 {resource}`.
- Use a short message, such as `No pods match the current filters.`
- A retry action uses the compact table action style and a label of at most two words.
- Long endpoint errors, stack traces, and operational evidence belong in a drawer, toast, or Activity Audit Log.

## 14. Pagination

Pagination follows `docs/design/components/PAGINATION.md`:

- default page size: 5;
- options: 5, 10, 25, 50;
- resource-aware summary;
- shared numeric pagination component;
- footer inside the table surface.

## 15. Responsive behavior

Keep the resource title, primary status, and row action accessible. Lower-priority columns may be hidden at narrow widths. Horizontal scrolling is acceptable for operational tables when hiding data would remove necessary context, but filters and pagination must not create page-level horizontal overflow.

## 16. Accessibility

- Associate the table with a visible heading or caption.
- Use `<th scope="col">` for column headers.
- Use `aria-sort` for sorting.
- Use `aria-current="page"` for active pagination.
- Use `aria-busy` for asynchronous table regions where practical.
- Provide `title` and `aria-label` for icon-only actions.
- Do not rely on color alone for status.
- Keep visible keyboard focus states.

## 17. Review checklist

A table is compliant when:

- the header, loading bar, filters, table, state, and pagination use the required order;
- column headings are Title Case and not force-uppercase;
- all columns are left aligned except the final action column;
- resource titles and supporting text use the standard hierarchy;
- semantic labels use the compact rectangular contract;
- visible row actions are compact, no more than two, and no more than two words each;
- filters have standard labels, fields, hover/focus states, and responsive layout;
- long detail is not forced into a row;
- the table defaults to five rows and uses the global pagination component;
- HTMX changes only the intended region and preserves relevant state.
