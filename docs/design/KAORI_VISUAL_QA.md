# KAORI Visual QA Standard

## Purpose

KAORI Visual QA converts visible UI quality into repeatable engineering evidence without replacing human design judgment.

It extends the existing Playwright browser authority and the KAORI Design System. It does **not** create a second browser framework, device-specific CSS standard, aesthetic score, or independent release authority.

The governing model is:

```text
Shared design contract
  -> deterministic browser geometry
  -> canonical viewport + theme evidence
  -> reviewed visual baseline evidence
  -> structured Visual QA findings
  -> human UAT for subjective acceptance
```

## Canonical Viewports

The executable viewport authority remains `tests/ui/conftest.py`:

| Name | Width | Height | Intent |
| --- | ---: | ---: | --- |
| large-desktop | 1440 | 900 | large desktop |
| laptop | 1280 | 800 | standard laptop |
| compact-laptop | 1024 | 768 | compact laptop |
| tablet | 768 | 1024 | tablet |
| mobile | 390 | 844 | phone |
| small-mobile | 360 | 800 | small phone |

Tests must reuse this authority rather than copy breakpoint values into page-local suites.

Real-device UAT remains additional evidence. A physical-device name must not become a CSS contract.

## Theme Matrix

Authenticated deterministic Visual QA covers both:

- Light mode.
- Dark mode.

Tests must switch theme through the same KAORI theme control used by operators. Test-only DOM class mutation is not an accepted substitute when the application control is available.

## Surface Inventory

`tests/ui/visual_audit.py::build_visual_surface_inventory()` derives the governed inventory from Flask route ownership plus canonical breadcrumb taxonomy.

Every discovered active GET surface is classified as one of:

- **deterministic** — executable with stable test-owned fixtures;
- **parameterized** — requires an object identifier or explicit route parameter;
- **runtime-dependent** — requires provider, live integration, or evidence not suitable for a deterministic fixture.

A surface must not disappear from audit scope merely because deterministic rendering is difficult.

The first executable deterministic catalog is intentionally bounded to stable representative surfaces:

- Welcome;
- Settings / General;
- Notification Center.

Expansion must add stable fixture authority before promoting another route from runtime-dependent to deterministic.

## Machine-Enforced Geometry

Reusable assertions live only in `tests/ui/visual_audit.py`.

Current machine-enforced invariants include:

- no page-level horizontal overflow;
- visible element rendered geometry must be non-zero;
- fixed/sticky surfaces must remain within the viewport;
- normal-flow primary actions must remain within document width;
- shared Hero descriptions must not horizontally overflow;
- Hero descriptions must render as one natural line on canonical non-phone viewports;
- phone Hero descriptions may wrap naturally;
- the shared primary-action marker is owned by canonical component primitives.

Machine assertions must express measurable layout facts. They must not encode subjective judgments such as whether a page "looks premium."

## Visual Baseline Authority

### Machine authority

The source-controlled `tests/ui/baselines/authenticated-visual.json` manifest stores normalized visual signatures and expected dimensions.

The signature is produced from a reduced, quantized visual thumbnail. This intentionally removes low-value raster/PNG encoding noise while preserving visible composition changes.

Ordinary CI must never rewrite this manifest.

The only update control is:

```text
KAORI_UPDATE_VISUAL_BASELINES=1
```

An update is valid only when produced through the governed capture path and reviewed as an intentional UI change.

### Human-review evidence

`.github/workflows/ui-visual-baseline-capture.yml` is the governed capture authority.

It must retain:

- login candidate evidence when requested;
- authenticated deterministic candidate evidence when requested;
- screenshots;
- Playwright traces when produced;
- structured Visual QA reports;
- baseline manifest candidates.

Baseline artifacts are review evidence. They do not silently become source authority.

## Finding Vocabulary

Visual QA uses exactly three finding states:

- **PASS** — executable invariant is satisfied and no visible refinement is requested.
- **Needs refinement** — usable and not broken, but human review identifies a visual-quality improvement.
- **Broken** — an executable geometry, baseline, interaction, or visible usability invariant fails.

Do not replace these states with numeric aesthetic scores.

## Human Visual-Review Rubric

Human review evaluates the candidate across the canonical viewport/theme evidence using the following rubric.

### Visual hierarchy

Check that page purpose, current state, primary action, supporting evidence, and secondary detail are visually ordered correctly.

A page should not force the operator to infer the primary task from equal-weight cards or competing headings.

### Typography hierarchy

Check title, section heading, body, metadata, label, technical value, and helper-text roles against canonical typography ownership.

Do not approve page-local font-size compensation for a layout problem.

### Spacing and rhythm

Check vertical rhythm, card spacing, section spacing, filter/action spacing, and repeated component cadence.

Dense operational data is allowed; accidental crowding is not.

### Alignment

Check shared left edges, table headers/cells, right-aligned action columns, card grids, Hero/content alignment, and control rows.

Misalignment that repeats across multiple surfaces should be fixed at shared-component authority.

### Density

Check whether the information volume matches the operator task and viewport.

Secondary explanation should move below the primary operational decision rather than expand the Hero or first viewport unnecessarily.

### Responsive recomposition

Check that smaller viewports recompose rather than merely shrink.

Validate navigation, Hero metadata/context, actions, filters, cards, tables, drawers, and dialogs without page-level horizontal scrolling.

### Hero composition

Check the canonical Identity -> Purpose -> Context -> Action hierarchy.

For #470-compatible Heroes, non-phone descriptions must remain one natural rendered line. Phone wrapping is allowed when readable and overflow-free.

### Cards, tables, and forms

Check canonical shell ownership, column/action alignment, filter geometry, pagination, field labels, focus states, and empty/loading/error presentation.

### Action prominence

The main operator action must be identifiable without competing equal-weight actions.

Destructive actions must retain semantic separation and confirmation patterns.

### Loading, empty, error, blocked, and degraded states

Check that states remain structurally aligned with the normal page and preserve the information required to understand the next action.

A state must not look like missing CSS or an unhandled partial render.

### Light/dark parity

Check that hierarchy, contrast, semantic tones, borders, surfaces, and visual emphasis remain equivalent across themes.

Dark mode is not a separate layout.

### Accessibility-visible concerns

Human review should flag visible focus loss, unreadable contrast, clipped text, color-only status communication, undersized touch targets, or unreachable controls.

Formal accessibility checks remain separate authorities.

### Shared-component ownership

When the same visual defect appears across multiple routes, remediation belongs in the canonical shared component or token unless a documented domain exception exists.

Page-local compensation is not the preferred fix.

## Evidence Report

Visual QA writes both:

- `visual-audit-report.json` for machine/process consumption;
- `visual-audit-report.md` for human review.

Each finding records:

- status;
- surface;
- viewport;
- theme;
- shared component or surface owner;
- violated/reviewed invariant;
- evidence reference.

When remediation becomes a separate work item, link the governing GitHub issue in the evidence/commentary rather than embedding Project metadata into the report.

## CI and Delivery Boundary

Normal work-branch Developer Check may run deterministic Visual QA when relevant paths select the UI test family.

The governed pre-UAT capture workflow exists for intentional broad visual evidence.

Delivery order remains:

```text
Issue
  -> work branch
  -> Developer Check
  -> PR to kaori/staging
  -> Staging Integration / Full Admission fallback
  -> governed Visual QA evidence for the candidate
  -> human UAT
  -> staging -> main promotion
```

Visual screenshots are never the only admission authority.

Security, functional, architecture, release-governance, migration, runtime, and other existing gates remain independent requirements.

## Human UAT Authority

Automation may conclusively identify measurable failures such as overflow, viewport escape, unexpected wrapping, or a changed reviewed visual signature.

Automation must not make the final subjective decision that a design is "good," "premium," "balanced," or aesthetically complete.

Human UAT remains final authority for:

- hierarchy preference;
- visual balance;
- perceived density;
- copy scanability beyond executable limits;
- interaction feel;
- whether an intentional visual change is acceptable.

A human UAT rejection becomes a new executable contract when the acceptance intent can be stated deterministically, as #470 did for Hero single-line rendering.

## Baseline Update Procedure

1. Start from a governed Issue and exact work branch.
2. Make the intentional UI change.
3. Pass exact-head Developer Check.
4. Run the governed visual baseline capture for the required scope.
5. Review screenshots and structured findings.
6. Update source-controlled manifest evidence only for accepted intentional changes.
7. Rerun Developer Check on the final exact head.
8. Merge only through the normal `kaori/staging` flow.
9. Obtain staging integration evidence and human UAT before promotion.

Never regenerate baselines merely to make a failing test green.
