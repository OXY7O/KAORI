# Kubernetes Operations Guidance Cards

## Expandable guidance header layout

Secondary guidance cards that use `components/view_more_content.html` must keep:

- icon at the far left;
- title aligned on the first row;
- description allowed to use the full content width under the title;
- collapse affordance aligned on the far right;
- on compact rails, the chevron remains visible while the `View Details` / `Collapse` label may hide to preserve title and description width.

This prevents titles and helper descriptions from collapsing into a narrow text column inside side rails such as ConfigMap and Secret operation workspaces.
