# KAORI Empty State

Use `app/templates/components/states/_empty_state.html` for full table, registry, workspace, and major card empty states.

## Contract

- Full table, registry, workspace, and major-card zero states use this shared component; page-local icon/title/description empty-state markup is not allowed for newly reviewed KAORI surfaces.
- Keep the empty state inside its owning table/card/workspace so the page header, filters, and pagination context remain stable.
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
- `No Results`: canonical data exists, but current search/filter state returns no rows.
- `Sync Required`: the source exists, but KAORI has no collected snapshot yet.
- `No Data`: neutral zero-result state when a more precise state is unavailable.
- A domain-specific healthy label such as `Queue Clear` may use `empty_state_tone='normal'` when zero rows are the expected healthy operating state.
- `Admin Required`: the current user cannot perform the setup action.

Do not use empty states to represent authorization failures, dependency blockers, validation failures, or runtime errors. Those conditions require their dedicated KAORI state patterns. In a table body, unavailable prerequisites use `components/states/_blocked_state.html` with `blocked_state_variant='table'`.

## HTMX and Fragment Rule

An empty state must not change the refresh contract of its owning region. If a workspace polls while populated, the same owning region remains the HTMX target while empty. HTMX out-of-band fragments are response-only helpers: do not render them inline during the initial full-page composition.

## Canonical State Architecture

KAORI has two canonical visual state components:

- `components/states/_empty_state.html` for initial empty, filtered no-result, and collected-data-empty conditions.
- `components/states/_blocked_state.html` for unmet prerequisites and unavailable dependencies.

Domain-specific templates may remain as parameter adapters only when a route renders that template directly or when many callers depend on its context contract. An adapter must only map domain context into canonical component parameters; it must not contain duplicate card, button, label, icon, or spacing markup.

Legacy visual partials must be deleted after their callers are migrated. The UI contract tests reject references to the removed analytics overview empty-state partial and reject duplicate visual markup in the approved blocker adapters.
