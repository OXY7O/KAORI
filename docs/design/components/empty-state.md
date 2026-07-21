# KAORI Empty State

Use `app/templates/components/states/_empty_state.html` for full table, registry, workspace, and major card empty states.

## Contract

- Titles and semantic labels use Title Case.
- Primary and secondary action labels contain no more than two words.
- A state exposes no more than two visible actions.
- Descriptions use one or two short sentences and name KAORI when KAORI is the acting product.
- Initial setup, filtered results, blocked prerequisites, unavailable dependencies, and healthy zero-result states must not share the same wording.
- Permission checks remain server-side. The component may hide actions and show `Admin Required`, but it does not replace route authorization.

## Parameters

```jinja
{% set empty_state_icon = "boxes" %}
{% set empty_state_label = "Setup Required" %}
{% set empty_state_title = "No Kubernetes Connections Found" %}
{% set empty_state_description = "Register a Kubernetes API connection so KAORI can discover capabilities and collect inventory." %}
{% set empty_state_action_url = url_for("cluster.add_cluster") %}
{% set empty_state_action_label = "Add Cluster" %}
{% set empty_state_action_icon = "plus" %}
{% set empty_state_permission = "clusters.manage" %}
{% set empty_state_show_admin_required = true %}
{% include "components/states/_empty_state.html" %}
```

Optional parameters include `empty_state_secondary_action_url`, `empty_state_secondary_action_label`, `empty_state_secondary_action_icon`, `empty_state_min_height`, `empty_state_container_class`, and `empty_state_variant`.

## Semantic Labels

- `Setup Required`: no canonical source is registered.
- `No Results`: data exists, but current filters return no rows.
- `Sync Required`: the source exists, but KAORI has no collected snapshot.
- `No Data`: neutral default when a more precise state is unavailable.
- `Admin Required`: the current user cannot perform the setup action.

Do not use empty states to represent authorization failures, dependency blockers, validation failures, or runtime errors. Those conditions require their dedicated KAORI state patterns.
