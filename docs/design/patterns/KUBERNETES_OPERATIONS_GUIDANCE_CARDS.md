# Kubernetes Operations Guidance Cards

## Compact side-rail headers

Expandable guidance cards placed in narrow Kubernetes Operations side rails use the shared `compact_action=true` contract.

The compact header must:

- keep the icon fixed at the far left;
- give the title and description the full available middle column;
- show only the chevron visually on the right;
- retain accessible `View Details` and `Collapse` text through screen-reader-only labels;
- keep the description below the title rather than squeezing both into a narrow horizontal flex row.

This contract applies to ConfigMap create/update/delete and Secret create/replace/delete guidance cards. Wide workspace cards may continue to show visible action labels.
