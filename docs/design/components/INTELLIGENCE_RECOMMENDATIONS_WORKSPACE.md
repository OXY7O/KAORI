# Intelligence Recommendations Workspace

## Canonical Composition

The Recommendations hero remains the Intelligence posture reference. The workspace below it uses:

1. A KAORI section header with the loading bar placed below the title/status row.
2. Auto-refresh HTMX filters with no Apply button.
3. A responsive recommendation table on desktop and compact cards on smaller screens.
4. One `View Details` modal action per recommendation; expandable inline evidence is not permitted.
5. Canonical pagination: the left footer group owns `Showing a–b of n` and `Rows`; the right group owns Previous, numeric pages, and Next.

## Filter And Pagination Contract

Search uses a short debounce. Select controls refresh on change. Filter requests:

- reset the result page to 1;
- replace only `#recommendations-results-content`;
- preserve the filter controls and current scroll position;
- update the browser URL;
- display the shared KAORI loading bar;
- cancel stale in-flight result requests;
- preserve non-HTMX GET fallback behavior.

Numeric pagination, Previous, Next, and page-size changes also replace only `#recommendations-results-content`. Pagination must use `show:none` and `focus-scroll:false` so result changes do not jump the operator back to the beginning of the workspace.

Reset is the only operation that replaces the complete `#recommendations-workspace-content`, because the form controls must return to their default state.

## Record Summary Contract

The primary Recommendation column shows a concise operational summary. Examples, long technical identifiers, and supporting evidence remain in the detail modal. The service owns summary compaction so desktop and mobile records use the same wording.

## Detail Modal Contract

Recommendation evidence is rendered through the shared resource-detail modal system with an Intelligence context label. The modal uses:

- concise title and summary;
- a four-cell evidence summary strip;
- `Finding Overview` and `Evidence Contract` as peer cards;
- compact `Affected Context` evidence cells;
- one full-width `Recommended Action` section;
- evidence-boundary and validation callouts at the bottom.

The main KAORI scroll container reserves a stable scrollbar gutter. Opening or closing the modal must not resize the page or shift the underlying workspace.
