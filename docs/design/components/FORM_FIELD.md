# KAORI Form Field Alignment Standard

## Purpose

Use the shared `components/form_field.html` primitive for form rows whose controls must align across peer columns, especially Cluster, Namespace, object identity, mutability, provider, and live-target selectors.

## Canonical Vertical Rhythm

Every peer field follows the same order:

```text
Label Row (min-height 24px)
↓ 8px
Input / Select (40px)
↓ 6px
Helper / Validation Copy
```

Rules:

- the label row reserves `min-h-6` for **every** field, including fields without status metadata;
- compact metadata such as `Live`, `Create Only`, or `Validated` belongs in the label row and must not push its control downward;
- the control starts directly after the label row using the canonical `mt-2` spacing;
- descriptive help belongs **below** the control, never between label and control;
- peer target controls use `h-10`; do not mix `h-10` and `h-11` in one grid row;
- disabled controls retain the same height and baseline as enabled controls;
- status meaning is never conveyed by color alone.

Canonical implementation:

```jinja
{% import "components/form_field.html" as form_field %}

<label class="block min-w-0">
    {{ form_field.label_row('Namespace', 'Live', 'normal', 'radio') }}
    <select class="{{ form_field.select_classes() }}">...</select>
    {{ form_field.help('Loaded directly from the selected Kubernetes API.') }}
</label>
```

## Scope

Current reviewed consumers include:

- ConfigMap Create / Update / Delete target fields;
- Secret Create / Replace / Delete target fields;
- Protected Secret Reveal target fields.

The same primitive should be considered when Integrations registration forms are DRY-refactored during their final recheck.

## Anti-Patterns

Do not:

- place helper text between the label and control;
- use a taller label only because one field has a status badge;
- solve alignment with page-local `mt-*` offsets;
- mix arbitrary input heights in one peer row;
- duplicate the canonical select/input utility bundle in newly reviewed form fields.
