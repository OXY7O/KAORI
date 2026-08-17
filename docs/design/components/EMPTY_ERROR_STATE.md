# Empty, Error, and Blocked State Standard

Use the state that describes the actual operational condition. Zero records are not automatically an error, and unavailable dependencies are not an empty state.

## Canonical ownership

- Empty / no-result / healthy-zero state: `app/templates/components/states/_empty_state.html`
- Blocked prerequisite or unavailable dependency: `app/templates/components/states/_blocked_state.html`
- Loading: the owning shared loading component or loading bar
- Mutation/runtime error: canonical operational feedback, blocker, or error surface; never a fake empty state

The detailed empty-state contract is documented in `docs/design/components/empty-state.md`.

## State selection

| Condition | Canonical state | Typical label |
|---|---|---|
| No source registered | Empty | `Setup Required` |
| Filters/search return zero rows | Empty | `No Results` |
| Source registered but no snapshot collected | Empty | `Sync Required` |
| Healthy operational zero state | Empty | Domain-specific healthy label, e.g. `Queue Clear` |
| Dependency/prerequisite unavailable | Blocked | `Source Unavailable` / `Setup Required` |
| Authorization failure | Route/permission boundary | Do not render as empty |
| Runtime or mutation failure | Operational feedback/error state | Do not render as empty |

Keep the state inside its owning surface so headings, filters, and pagination context remain visible. Table pagination summaries remain visible for zero results. Titles use Title Case; descriptions use sentence case. Technical detail belongs in a drawer, toast, Activity Audit, or diagnostic surface rather than the empty-state description.

For table-body blockers, use `blocked_state_variant='table'` so blocker geometry matches the canonical table zero-state footprint without duplicating page-local markup.
