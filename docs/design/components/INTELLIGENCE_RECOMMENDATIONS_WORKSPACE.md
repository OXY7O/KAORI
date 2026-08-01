# Intelligence Recommendations Workspace

## Canonical Composition

The Recommendations hero remains the Intelligence posture reference. The workspace below it uses:

1. A KAORI section header with an in-header loading bar.
2. Auto-refresh HTMX filters with no Apply button.
3. A responsive recommendation table on desktop and compact cards on smaller screens.
4. One `View Details` modal action per recommendation; expandable inline evidence is not permitted.
5. Canonical pagination: `Showing a–b of n`, `Rows`, Previous, numeric pages, and Next.

## Filter Contract

Search uses a short debounce. Select controls refresh on change. Every filter operation:

- resets the result page to 1;
- replaces only `#recommendations-workspace-content`;
- updates the browser URL;
- displays the shared KAORI loading bar;
- preserves non-HTMX GET fallback behavior.

## Detail Contract

Recommendation evidence is rendered through the shared resource-detail modal system with an Intelligence context label. The table remains concise; rule keys, conditions, impacts, affected evidence, and remediation steps belong in the modal.
