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

Icons are optional and must carry meaning. Do not add an icon to every cell or use decorative icons that do not improve interpretation. When a title cell contains two text lines, use a 40 px icon container with an 18 px icon so the visual weight matches the combined title and supporting line. For a single text line, use a 32 px container with a 16 px icon. The icon remains vertically centered against the complete text group, not only the first line.

## 8. Row data and typography

All table content uses the same application font family. A table must not mix unrelated font families, monospace text, or arbitrary font sizes unless a technical value explicitly requires monospace presentation. The default body value is 14 px with regular or medium weight. Visual hierarchy is created only through the approved levels: 14 px semibold for a primary resource title, 14 px regular/medium for ordinary values, 12 px muted for supporting context, 11–12 px semibold for column headers, and 10 px semibold for compact labels.

Two patterns are permitted:

- text-only for direct values;
- icon + text when the icon adds operational meaning.

Use one pattern consistently within a column when it improves scanning, but do not force every row value to begin with an icon. Icon use is contextual: identity, security, time, provider, and externally linked values may benefit from an icon; ordinary counts, names, timestamps, versions, and direct values usually remain text-only. Labels are also contextual rather than mandatory. Use a label only when the value represents a compact status, state, category, severity, or metadata token that benefits from visual distinction. Plain operational data remains plain text.

Technical detail that would make the row dense belongs in an expandable row, drawer, modal, or detail page.

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

Standard status labels use the global semantic palette with a soft background and semantic text. They are borderless. Use `table_label.status_label(...)` for text-first status and `table_label.status_indicator_label(...)` when a small status dot improves scanning.

Metadata labels use borderless Violet or neutral context styling through `table_label.metadata_label(...)`. Timestamps stay plain text.

A compact icon + border treatment is an explicit exception for a special posture, eligibility, security, or high-attention state. It must use `table_label.special_label(...)`. Do not add borders or icons to ordinary status labels inline.

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

All ordinary non-CRUD table actions share one neutral utility appearance and the same hover, focus, disabled, and active behavior. Do not assign different colors to `Open`, `View Details`, `Manage`, `Retry`, `Validate`, or similar routine controls merely to distinguish their labels.

CRUD actions may use semantic treatment when needed: `Create` normally belongs at block or page level; `Edit` may remain neutral or use the standard mutation treatment; `Delete` uses Critical styling. The geometry must remain consistent across all variants.

Two visible row actions remain the preferred default because they preserve scanability. More than two are permitted when all actions are high-frequency, labels remain at most two words, the row has enough width without wrapping, the action group does not dominate the data, and the result remains visually balanced at supported desktop widths. Otherwise, move secondary actions into a `More` menu. Icon-only controls require both `title` and `aria-label`.

## 11. Filter bar

Filter field groups use the canonical `table_ui.filter_layout_classes()` layout. `registry_ui.filter_form(...)` applies the same layout automatically. Page-local fixed desktop grids (`lg:grid-cols-*`, `xl:grid-cols-*`, or fixed-width search/select columns) are not the default filter geometry.

The canonical layout is full-width and content-aware:

- every visible direct filter field participates in the available row width;
- fields wrap when the viewport cannot preserve a practical control width;
- when a wrapped row contains fewer fields, those fields expand to consume the remaining row width instead of leaving an orphan empty column;
- two visible filters fill the row as two peers, three filters fill it as three peers, and a single remaining filter fills its row;
- hidden inputs do not reserve layout space;
- explicit action groups may remain content-width when the filter surface includes `Apply`, `Clear Filters`, or another operator action; the filter fields still consume all remaining width;
- `Clear Filters` keeps one interaction owner (`components/table_registry.html`) across table, registry, and visualization filter surfaces;
- visualization filters that become active client-side keep the canonical action hidden with the HTML `hidden` state until a real filter/search value is active; JavaScript toggles that semantic state rather than relying on competing display utility classes;
- when a filtered surface already has a block/header action group, `Clear Filters` belongs in that same header action group beside metadata/context actions; do not float it in a separate row above the filter fields;
- inside a right-aligned header/action group, `Clear Filters` is the leading action: it appears immediately before existing permanent actions or context labels so activating filters never pushes, displaces, or visually collides with those controls;
- the shared `clear_filters_action(...)` owns that leading-order behavior; consumers must not reproduce it with page-local ordering utilities;
- when no header action group exists, `Clear Filters` may sit beside the filter fields as a compact action while the fields continue to consume the remaining width; the clear action stays content-width and must not consume an equal filter-field column;
- filters never use `max-w-*` merely to keep a control visually narrow inside an otherwise empty filter row.

On smaller screens the same contract stacks or wraps without page-level horizontal overflow. This full-width fill behavior is the KAORI default for Inventory, Integrations, Access, Intelligence, Reports, Governance, and Platform Operations filter surfaces.

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

Dense Inventory filter rows use the short field label `Search` and a concise domain-specific placeholder, for example `Name, IP, owner, or node`. Other workspaces may retain a resource-specific search label when the surrounding context is ambiguous. A filter or search change resets the table to page 1 and preserves all other relevant state.

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
- resource titles and supporting text use the standard hierarchy, with a larger icon container when two text lines are present;
- icons and semantic labels are used only when they improve meaning; semantic labels use the compact rectangular contract;
- visible row actions are compact, normally limited to two, use no more than two words each, and exceed two only when the documented fit and usability conditions are satisfied;
- filters have standard labels, fields, hover/focus states, and responsive layout;
- long detail is not forced into a row;
- the table defaults to five rows and uses the global pagination component;
- HTMX changes only the intended region and preserves relevant state.


## 18. Design judgment and exceptions

The table standard is a consistency system, not a requirement to decorate every value. Designers and implementers must prioritize scanability, information density, and semantic meaning. When choosing between icon + text, label, or plain text, use the least visually heavy representation that still communicates the value correctly. Any exception must preserve the shared typography scale, alignment, spacing, interaction states, and accessibility contract.
