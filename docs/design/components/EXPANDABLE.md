# Expandable Content Standard

The canonical implementation and decision rules are defined in `VIEW_MORE_CONTENT.md`.

Summary:

- Secondary guidance and reference content use `components/view_more_content.html` through a semantic wrapper.
- Expandable titles use Title Case and the shared 14 px semibold hierarchy.
- Supporting descriptions use sentence case and the shared 12 px hierarchy.
- Default state is closed unless immediate visibility is operationally necessary.
- Required fields, blockers, readiness requirements, critical errors, and primary request previews must remain visible.
- Primary ordered workflows use `components/info_flow.html` rather than generic expandable content.
- The trigger preserves native `details`/`summary` behavior, visible focus, and accessible expanded state.
