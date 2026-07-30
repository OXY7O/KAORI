# KAORI Styling Baseline Audit — July 2026

## Objective

Establish a reusable, DRY styling contract before continuing page-by-page standardization. This audit records the current implementation baseline, distinguishes canonical components from review candidates, and adds automated ceilings so style drift cannot increase unnoticed.

## Confirmed Canonical Components

The codebase already contains reusable foundations for:

- hero: `components/page_hero.html`;
- pagination: `components/pagination.html`;
- tables: `components/table.html`;
- compact labels: `components/table_label.html`;
- primary ordered flow: `components/info_flow.html`;
- related destination: `components/related_page_card.html`;
- action buttons and form footer: `components/action_button.html`, `components/form_action_bar.html`;
- page context, workspace summary, loading, empty, and error states.

The main issue is not absence of a design system. It is inconsistent adoption and repeated page-local utility bundles.

## Changes Introduced by This Audit

1. Added `KAORI_STYLING_GUIDE.md` as the practical canonical entry point.
2. Added a shared 20rem right-side rail geometry in `components/context_rail.html`.
3. Added a shared View More Content shell in `components/view_more_content.html`.
4. Refactored Information Guide Card and Context Guidance Card to reuse the shared expandable shell.
5. Clarified the label contract:
   - standard status labels are borderless;
   - metadata labels are borderless;
   - status-dot labels remain borderless;
   - icon + border is an explicit special-label exception.
6. Added `table_label.special_label(...)` for that exception.
7. Added `scripts/verify_ui_style.py` and a per-template style ceiling.

## Current Review-Candidate Counts

The initial style scan covers 270 templates and reports:

| Metric | Count | Interpretation |
|---|---:|---|
| Arbitrary text-size utilities | 729 | Includes approved shared-component values and page-local review candidates. New page-local arbitrary sizes are prohibited. |
| Arbitrary or oversized radii | 1 | Must be reviewed and removed unless semantically justified. |
| Raw hex colors in templates | 3 | Must migrate to semantic tokens. |
| Raw palette utilities | 982 | Includes existing legacy utilities; page reviews should replace them with semantic tokens. |
| Semantic border utilities | 321 | Not all are labels. Review whether each is a status container, special label, or unnecessary border. |
| Page-local compact status labels | 24 | Priority migration target to `table_label` macros. |
| Custom hero titles | 4 | Review exceptions such as authentication/PDF surfaces; authenticated pages must use the shared hero. |
| Custom Previous/Next pagination pairs | 0 detected by the conservative rule | Continue using the shared pagination component. |
| Repeated standard surface shells | 157 | Includes legitimate content shells and copied bundles; review page by page rather than mass-replacing without semantic context. |
| Copied standard right-rail grids | 0 at baseline | Future implementations must use `context_rail.html`. |

These counts are ceilings, not a claim that every occurrence is defective. The baseline prevents increases and forces an explicit update whenever a page review reduces the count.

## Key Findings

### Typography

The hierarchy is documented, but page templates still contain many arbitrary text sizes. The approved approach is to keep exceptional values inside shared components and use semantic Tailwind scale values in domain templates.

### Labels

`table_label.status_label(...)` and `metadata_label(...)` are already borderless. The missing contract was an explicit special-label component for the limited icon + border case. That exception is now implemented instead of encouraging inline badge variants.

### Hero

Hero geometry and typography are centralized in `page_hero.html`. Page review must focus on adoption and excessive hero content, not new hero variants.

### Pagination

The numeric pagination component and page-size contract already exist. Future work is adoption verification and removal of local footer geometry.

### Right-Side Boxes

Semantic components already exist, but the column geometry was still copied locally. `context_rail.html` now owns the standard 20rem split and spacing. Box selection is based on purpose, not visual preference.

### View More Content

Information Guide Card and Context Guidance Card duplicated the same expandable header. They now reuse one shared shell. Primary flows remain separate in Info Flow because they have a different semantic purpose and visual hierarchy.

### Tables and Cards

Many templates repeat standard card-like utility bundles. A mass replacement would be unsafe because not every surface is a table. The migration must be page-by-page, selecting the correct semantic component rather than creating one generic card abstraction for unrelated content.

## Migration Priority

1. Main module landing and overview pages.
2. High-traffic operational registries and inventory pages.
3. Create/edit/manage workflows with right contextual rails.
4. Detail pages and expandable evidence.
5. Lower-frequency settings and support pages.
6. Authentication and PDF surfaces as separately documented exceptions.

## Acceptance Gate for Each Page

A page is considered standardized when:

- it uses the canonical hero or a documented non-authenticated exception;
- titles and descriptions follow the font hierarchy;
- compact labels use shared macros;
- right-side layout and boxes use shared components;
- tables and pagination use shared contracts;
- required information is visible and secondary content uses the shared expandable shell;
- no new raw palette, arbitrary radius, inline style, inline event handler, or page-local script debt is added;
- the per-file style baseline is reduced or unchanged;
- relevant contract tests pass.
