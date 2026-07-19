# Accessibility Standard

All interactive controls require visible focus, meaningful labels, and keyboard access. Icon-only actions require `title` and `aria-label`. Current pagination uses `aria-current="page"`; sortable columns use `aria-sort`; loading regions expose `aria-busy` where appropriate.

Semantic state is communicated by text plus color, and optionally icon. Contrast must remain readable in light and dark modes.
