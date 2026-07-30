# Form and Filter Standard

Form and filter labels use Title Case, 12 px semibold. Values use 14 px regular. Helper and validation text use 12–14 px sentence case.

Page-level form inputs and selects use a 40 px minimum height, `rounded-lg` geometry, soft border, visible Violet focus ring, and contextual placeholder. Selects and action controls use pointer cursors; disabled controls use cursor-not-allowed. Compact table-filter controls are the documented exception and use `rounded-md` through `components/table.html`.

Desktop filter groups remain on one row when space permits. Mobile layouts stack without horizontal page overflow.

## Form Action Footer

Create, edit, and configuration forms use the shared Form Action Bar for their final action region. The helper beside the action is one sentence, normally no more than 72 characters, and communicates only the immediate condition or consequence of submission.

Detailed workflow, readiness, and remediation content belongs in Connection Validation Header, Info Flow, field helper text, or validation evidence. See `FORM_ACTION_BAR.md`.

