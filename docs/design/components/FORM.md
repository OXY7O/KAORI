# Form and Filter Standard

Form and filter labels use Title Case, 12 px semibold. Values use 14 px regular. Helper and validation text use 12–14 px sentence case.

Page-level form inputs and selects use a 40 px minimum height, `rounded-lg` geometry, soft border, visible Violet focus ring, and contextual placeholder. Selects and action controls use pointer cursors; disabled controls use cursor-not-allowed. Compact table-filter controls are the documented exception and use `rounded-md` through `components/table.html`.

Desktop filter groups remain on one row when space permits. Mobile layouts stack without horizontal page overflow.

## Form Action Footer

Create, edit, and configuration forms use the shared Form Action Bar for their final action region. The helper beside the action is one sentence, normally no more than 72 characters, and communicates only the immediate condition or consequence of submission.

Detailed workflow, readiness, and remediation content belongs in Connection Validation Header, Info Flow, field helper text, or validation evidence. See `FORM_ACTION_BAR.md`.
## Form Layout Selection

KAORI supports two primary form-layout choices.

- **Form + Right Context** — use for focused create/edit/register/configuration tasks with one dominant form and concise supporting guidance. Geometry is the canonical Integration-style `8/12 + 4/12` split owned by `components/form_with_context_rail.html`. See `FORM_WITH_CONTEXT_RAIL.md`.
- **Full-width or specialized workspace** — use when the form is secondary to wide evidence, protected workflows, inspectors, tables, or domain-specific visual composition.

Do not remove a useful context rail only to stretch the previous card layout across the page. Do not invent a third form geometry when an approved pattern already fits.

