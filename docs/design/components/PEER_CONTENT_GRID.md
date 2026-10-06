# Peer Content Grid

## Purpose

`components/peer_content_grid.html` owns the responsive grid used when both columns are primary page content. It prevents dashboard templates from misusing the fixed 20rem right context rail for peer operational sections.

## Canonical API

```jinja
{% import "components/peer_content_grid.html" as peer_content_grid %}

<div class="{{ peer_content_grid.layout_classes() }}">
    <div class="{{ peer_content_grid.column_classes('primary') }}">...</div>
    <div class="{{ peer_content_grid.column_classes('secondary') }}">...</div>
</div>
```

For a 7/5 split:

```jinja
<div class="{{ peer_content_grid.layout_classes() }}">
    <div class="{{ peer_content_grid.column_classes('primary', 'seven-five') }}">...</div>
    <div class="{{ peer_content_grid.column_classes('secondary', 'seven-five') }}">...</div>
</div>
```

## Geometry

- Both columns stack below `xl`.
- Desktop gap is 20 px.
- Equal split uses 6/6 columns.
- Emphasized split uses 7/5 columns.
- Both blocks remain primary content and may contain metrics, charts, tables, or operational guidance.
- The grid row follows the tallest peer block.
- Both direct peer sections must use `h-full`; asynchronous wrapper elements use `h-full w-full` so the shorter card stretches to the same height.

## Decision Rule

Use Peer Content Grid when both blocks answer the current tab's primary question.

Use Right Context Rail only when the right side is supporting context that must not compete with the primary workflow. The rail must not contain a peer dashboard chart, a peer status summary, or a main operational block.
