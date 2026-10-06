# KAORI Form + Right Context Standard

## Purpose

Use **Form + Right Context** when the page is primarily a create, edit, register, or configuration task and the user benefits from concise supporting workflow, safety, compatibility, or related-workspace guidance beside the form.

This is an approved KAORI page-layout option. It is not a fallback and it is not interchangeable with the generic fixed-width Right Context Rail.

Canonical geometry is owned by:

```jinja
{% import "components/form_with_context_rail.html" as form_context %}
```

```jinja
<form class="{{ form_context.layout_classes() }}">
    <section class="... {{ form_context.main_classes() }}">
        ... primary form ...
    </section>
    <aside class="{{ form_context.rail_classes() }}">
        ... contextual side boxes ...
    </aside>
</form>
```

## Canonical References

Current visual references are:

- Register Kubernetes Connection
- Register Metrics Source
- Register Alertmanager Connection
- Create Kubernetes ConfigMap
- Update Kubernetes ConfigMap
- Delete Kubernetes ConfigMap
- Create Kubernetes Secret
- Replace Kubernetes Secret Data
- Delete Kubernetes Secret
- Protected Kubernetes Secret Reveal — New Request

The three Integration registration pages are the original visual references. Kubernetes Operations now consumes the formal shared contract across reviewed ConfigMap CRUD, Secret CRUD, and the Protected Reveal New Request task. Alertmanager currently retains a minor legacy gap variation; its Integrations final recheck should normalize that spacing while preserving the accepted composition.

During the Integrations final recheck, their copied `8/12 + 4/12` geometry should be replaced by the shared component **without changing the task hierarchy or interaction behavior**.

## Geometry

Desktop `xl` layout:

- layout: 12-column grid;
- primary form: 8 columns;
- context rail: 4 columns;
- column gap: 24 px;
- rail is sticky at `top-5`;
- rail boxes use intrinsic height and `16 px` vertical spacing.

Canonical classes:

```text
grid gap-6 xl:grid-cols-12 xl:items-start
min-w-0 xl:col-span-8
min-w-0 space-y-4 xl:col-span-4 xl:sticky xl:top-5
```

Below `xl`, semantic order is preserved:

```text
Primary Form
↓
Context Guidance
```

Do not introduce a page-local breakpoint, percentage split, or fixed rail width for this pattern.

## Primary Form Contract

The left side is the task surface. Prefer **one primary form card** with internal semantic sections instead of several peer cards stacked vertically.

Recommended internal order:

1. Identity / Target
2. Access / Endpoint / Payload / Configuration
3. Validation evidence or current state
4. Final Form Action Bar

The exact sections remain domain-owned.

Final create/save/apply/delete actions remain in the primary form. Do not place the mutation action in the right rail.

## Right Context Contract

The right side contains supporting information only. Use one to three canonical boxes.

Preferred order:

1. `Info Flow` for the primary ordered task sequence.
2. `Related Page Card` when one operational destination materially helps the task.
3. `Information Guide Card` or `Context Guidance Card` for secondary safety, compatibility, access, or post-save guidance.

Do not place the following in the rail:

- primary form fields;
- destructive confirmation controls;
- large tables or charts;
- duplicate validation output;
- the only copy of required error evidence;
- multiple unrelated destination actions.

## Layout Selection

### Choose Form + Right Context

Use when all are true:

- the page is a focused mutation or registration task;
- one primary form should remain visually dominant;
- supporting guidance is useful but secondary;
- context can fit into one to three intrinsic-height boxes.

Typical examples:

- Add/Register connection;
- Create ConfigMap;
- ConfigMap create/update/delete;
- Secret create/replace/delete;
- Protected Reveal New Request when target/request controls benefit from secondary policy guidance;
- provider configuration forms.

### Choose Full-Width Workspace Instead

Use when the task requires wide evidence, tables, inspectors, visualizations, or a specialized protected workflow whose content cannot remain secondary.

Typical examples:

- analytics and topology;
- full resource registries;
- Protected Reveal request registries (`My Requests` / `Approvals`), which remain full-width data views;
- certificate evidence workspaces;
- complex TLS rotation flows after their dedicated review.

The existence of a right-side component does not mean every page must use this pattern.

## DRY Ownership

- Layout geometry: `components/form_with_context_rail.html`
- Ordered side guidance: `components/info_flow.html`
- Related destination: `components/related_page_card.html`
- Secondary reference: `components/information_guide_card.html`
- Secondary ordered guidance: `components/context_guidance_card.html`
- Final form actions: `components/form_action_bar.html`

Do not duplicate the `xl:grid-cols-12`, `xl:col-span-8`, or `xl:col-span-4` geometry in newly reviewed pages.

Existing Integration pages may retain their copied geometry until their scheduled final recheck. Their visual contract must remain identical to this standard, and their migration to the shared component must be behavior-neutral.

## Accessibility and Responsive Rules

- DOM order is primary form first, context rail second.
- The rail cannot contain required information that is unavailable elsewhere to screen-reader or narrow-layout users.
- Sticky behavior begins only at the desktop split.
- Every side-box control follows its own keyboard/focus contract.
- The primary form retains one authoritative submission region.
- No horizontal page overflow at supported narrow widths.

## Anti-Patterns

Do not:

- remove a useful rail and simply stretch old cards to full width;
- create a new `18rem`, `20rem`, `22rem`, percentage, or arbitrary-grid task family when this standard fits;
- copy Integration geometry into another new template;
- use the rail as a second main workspace;
- repeat the same safety or workflow explanation in Hero, form, and rail;
- stretch rail cards to match the main form height.

## Review Checklist

- Shared `form_with_context_rail` geometry is used for newly reviewed consumers.
- Primary form is one dominant task surface.
- Main/action ownership remains on the left.
- Rail has one to three canonical supporting boxes.
- `Info Flow` remains the primary ordered sequence when needed.
- Layout stacks in semantic order below `xl`.
- Light/dark, 14-inch, narrow viewport, focus, validation, loading, and error states are checked.
- No page-local layout family is introduced.

## Form Field Alignment Contract

Form + Right Context pages use a single target-field baseline. The canonical primitive is `components/form_field.html`.

Rules:

- every label row reserves `min-h-6`, including fields without a status badge;
- `Live`, `Create Only`, or similar compact metadata belongs in that label row and must not push the control downward;
- the control begins immediately after the label row with the canonical `mt-2` spacing;
- descriptive/help copy is rendered **below** the control, never between label and control;
- target selects use the same `h-10` control height across ConfigMap, Secret, and Protected Reveal workflows;
- a grid row must not mix `h-10` and `h-11` controls.

This keeps Cluster, Namespace, object-name, mutability, and live-target selectors vertically aligned on desktop while preserving semantic stacking on narrow viewports.
