# Kubernetes Operations Guidance Cards

## Compact rail action

Expandable guidance cards placed in narrow operation rails use `compact_action=true`.

The compact variant:

- keeps only the chevron visible;
- removes `View Details` and `Collapse` text from the rail header;
- preserves the native `<summary>` interaction and accessible label;
- gives title and description the maximum available width;
- keeps full action text available for wider workspace usages where it adds value.

This is the canonical presentation for ConfigMap and Secret operation guardrail cards when placed in a narrow context rail.
