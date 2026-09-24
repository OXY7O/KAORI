# KAORI Foundation and Content-Density Matrix

**Parent authority:** #572  
**Workstream:** #607  
**Scope:** Foundation selection, density, and presentation decisions only

## Purpose

This document is the single Design System v2 decision matrix for KAORI foundation and content-density rules. It consolidates how an implementer selects existing brand/color, typography, spacing, shape/elevation, icon, copy-density, and technical-value authorities without creating a parallel token or typography system.

`KAORI_DESIGN_SYSTEM.md` remains the authoritative global visual and interaction contract. Detailed component documents remain normative for their owning component. This matrix resolves selection and density questions; it does not supersede those detailed contracts.

## Authority Boundary

| Concern | Current authority | Implementation / enforcement owner |
| --- | --- | --- |
| Global visual and interaction rules | `KAORI_DESIGN_SYSTEM.md` | shared design contracts |
| Design tokens and light/dark functional values | `frontend/styles.css` | semantic utilities consumed by shared components |
| Brand and operational semantic color | `components/COLOR_AND_SEMANTIC.md` | semantic token usage; no raw template hex |
| Dark-mode surface hierarchy | `components/DARK_MODE.md` | `scripts/verify_dark_mode_standard.py` + dark-mode contract tests |
| Typography roles and casing | `components/TYPOGRAPHY.md` | shared component typography + existing design/style contracts |
| Hero copy and typography | `components/HERO.md` | shared `page_hero` implementation + Hero verifier/contracts |
| Spacing rhythm | `components/SPACING.md` | shared component geometry + existing UI style/reuse checks |
| Shape and elevation | `KAORI_DESIGN_SYSTEM.md` + owning component contract | shared component geometry |
| Icon hierarchy | `components/ICONS.md` | owning shared component |
| Tables and compact labels | `components/TABLE_AND_LABEL.md` | shared table/label components + existing style contracts |
| Technical values | `components/TECHNICAL_VALUE.md` | `components/technical_value.html` |
| Dense metadata collections | `components/TECHNICAL_METADATA_COLLECTION.md` | `components/technical_metadata_collection.html` |

Historical lock and audit documents remain evidence only. A module may define semantic content, but it may not redefine foundation tokens, type scale, radius, elevation, or density.

## Foundation Decision Matrix

| Foundation question | Decision |
| --- | --- |
| Which color should a page use? | Use functional `surface-*`, `content-*`, `outline-*`, brand, or semantic status tokens. Never invent page-local raw colors when a semantic token exists. |
| How is Violet used? | Identity, focus, selection, primary interaction, contextual metadata, and restrained analytical emphasis. It does not replace operational status colors. |
| How do light and dark mode differ? | They keep the same functional token names. Dark mode is neutral-first with controlled Violet; page-local dark palettes are prohibited. |
| Which font family is default? | Global Inter / `font-sans`. Monospace is an explicit technical exception, not a second application hierarchy. |
| How is density solved? | Correct copy, layout, wrapping, or component choice first. Do not shrink page-local type or spacing to force content to fit. |
| Which spacing scale applies? | Use the shared Tailwind rhythm `4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 px` and the owning component contract. |
| Which radius applies? | 6 px compact controls/labels, 8 px ordinary controls, 12 px standard cards/supporting surfaces, 16 px major grouped/shell surfaces. Full radius is semantic-only. |
| How is elevation expressed? | Flat for internal sections/tables, Card for standard content surfaces, Elevated for menus/dialogs/drawers/floating panels. Dark mode favors surface/outline separation over heavy shadow. |
| When is an icon used? | Only when it improves identity, meaning, action recognition, or state scanning. Icons are contextual, never mandatory decoration. |
| How are technical values shown? | Proportional KAORI typography by default; exact casing preserved; monospace only when character alignment materially helps verification. |

## Typography Role Matrix

| Semantic role | Baseline | Density / wrapping rule |
| --- | --- | --- |
| Hero title | shared `page_hero.title_classes()` | Owns page identity; never locally shrunk to fit |
| Major page title outside Hero | `text-2xl`, semibold | Wrap naturally when necessary; keep hierarchy intact |
| Section title | `text-lg`, semibold | Title Case; no decorative uppercase/tracking |
| Card / table-block / modal title | `text-base`, semibold | Prefer concise Title Case; do not create smaller local variants |
| Subsection / expandable title | `text-sm`, semibold | Preserve semantic level across peer blocks |
| Ordinary body | `text-sm` | Sentence case; comfortable readable line height |
| Supporting/helper text | `text-xs`, or owning component `text-sm` | Secondary/muted; do not reduce below the documented role for density |
| Table header / form label | `text-xs`, semibold | Title Case; no arbitrary tracking |
| Compact table action | `text-xs`, medium | Keep the label concise and avoid wrapping where practical |
| Compact semantic label | shared label component only | 10 px semibold; short state/category text only |
| Technical value | `text-xs` to `text-sm` | Preserve source casing; monospace only for explicit verification-oriented values |

Typography may step down only where the owning responsive component documents that behavior. A page may not introduce arbitrary sizes such as `text-[13px]` or reduce a semantic role merely to solve local density.

## Copy-Density Matrix

| Surface | Copy contract | Overflow / detail rule |
| --- | --- | --- |
| Hero | One page identity plus one concise action-oriented description. Hero descriptions remain 7–15 words, preferably 8–12, no more than 68 characters, one complete sentence, and no manual line break. | Natural one-line rendering at canonical non-phone widths is browser-verified; remediation detail belongs below the Hero. |
| Standard card / content block | Title Case title plus short sentence-case description when explanation is needed. | Move lengthy explanation into the body, expandable guidance, drawer, or detail surface instead of shrinking typography. |
| Table block header | Title Case title plus short muted description, normally one line and never more than two. | Header actions wrap below the title on narrow screens; the description is not locally font-shrunk. |
| Resource/title cell | One primary line plus at most one optional supporting identity line. | Long primary values use the owning table truncation/title behavior; dense technical detail moves to row expansion, drawer, modal, or detail page. |
| Action button | Title Case action label; compact row actions use at most two words where practical. | Two visible row actions remain the preferred default; secondary actions move to `More` when density or wrapping becomes excessive. |
| Status / metadata label | Short state, severity, category, or metadata token only. | Versions, counts, timestamps, namespaces, names, and ordinary values remain plain text unless a semantic distinction requires a label. |
| Empty / blocked state | Title Case title plus concise sentence-case explanation. | Technical diagnostics belong in Activity, toast, drawer, or diagnostic surfaces rather than the state description. |
| Technical metadata collection | Key/value evidence with explicit wrapping. | `overflow-wrap:anywhere`; no nested vertical scroll; long metadata expands the owning detail surface. |

### Copy-density guardrail

Density problems are resolved in this order:

1. remove redundant copy;
2. move secondary detail to an existing detail/guidance surface;
3. use the correct shared component or page archetype;
4. allow the documented wrap/truncation behavior;
5. only then consider a documented component-level exception.

Never fix density with page-local font shrinking, arbitrary tracking, hidden critical evidence, or one-off spacing values.

## Spacing and Density Matrix

| Relationship | Standard rhythm |
| --- | --- |
| Hero to first section | 32 px |
| Major sections | 24–32 px |
| Card/block internal sections | 20–24 px |
| Related controls | 12–16 px |
| Label to control | 6–8 px |
| Inline icon to text | 6–8 px |

KAORI uses comfortable-compact operational density at 100% browser zoom. Compact density is valid only when the owning shared component documents it, such as compact table controls/labels, dense metadata variants, or other explicitly registered technical surfaces. A page-local compact mode is not an accepted workaround.

## Shape and Elevation Matrix

| Surface family | Radius / elevation rule |
| --- | --- |
| Compact table filters/actions, pagination, status/metadata labels | `rounded-md` / 6 px; flat or component-owned |
| Form controls, action buttons, navigation rows, ordinary icon surfaces | `rounded-lg` / 8 px |
| Standard cards, dropdown/menu surfaces, expandable supporting content | `rounded-xl` / 12 px; Card elevation where required |
| Sidebar frame, application frame, Hero, primary Info Flow, Related Page Card, large grouped surfaces | `rounded-2xl` / 16 px |
| Avatars, status dots, toggles, progress tracks | Full radius only because the shape is semantically appropriate |
| Menus, dialogs, drawers, floating panels | Elevated layer; restrained shadow and semantic outline/surface separation |

`rounded-3xl`, arbitrary authenticated-shell radii above 16 px, page-local heavy shadow, and pill-shaped status/metadata labels are prohibited unless a separately documented semantic component owns the exception.

## Icon Matrix

| Role | Standard size |
| --- | --- |
| Hero | 24 px |
| Card / major block | 20 px |
| Section / table block | 18 px |
| Resource title | 16–18 px |
| Inline / action | 14–16 px |
| Status label | 12 px |

For table title cells, use the established 40 × 40 px container with an 18 px icon for two-line identity and 32 × 32 px with a 16 px icon for one-line identity. Do not add an icon to ordinary counts, timestamps, versions, or values solely for decoration.

## Semantic Color and Theme Matrix

| Meaning | Family / rule |
| --- | --- |
| Brand / primary interaction | KAORI Violet |
| Healthy / Ready / Connected / Active | Normal |
| Informational / Pending / Syncing / Processing | Info |
| Warning / Degraded / Partial / At Risk / Maintenance / Paused / Silenced | Warning |
| Critical / Failed / Down / Blocked / Destructive | Critical |
| Unknown / Not Collected / Disabled / Inactive / Not Configured | Neutral |

Aggregated precedence remains `Critical > Warning > Info/Pending > Neutral/Unknown > Normal`. Missing data never renders as healthy. Status is communicated with text and, when useful, an icon; color is never the only signal.

Dark mode preserves the same semantic meanings and functional token names. The exact neutral surface stack, Hero exception, sidebar treatment, and controlled Violet allocation remain owned by `components/DARK_MODE.md` and `frontend/styles.css`.

## Technical-Data Presentation Matrix

| Data shape | Presentation |
| --- | --- |
| Ordinary IP, version, architecture, runtime, namespace, or technical value | Proportional KAORI typography; exact source casing |
| Hash, raw-copy identifier, command, code fragment, verification-sensitive value | Shared technical-value component with `monospace=true` only when alignment materially helps |
| Long raw identifier | Selectable; may break across lines; no conversion to label/pill |
| Labels / annotations / selectors / long key-value collections | Shared Technical Metadata Collection with explicit wrapping and no nested vertical scroll |

Technical presentation must not imply status. A technical value becomes a semantic label only when the value itself represents a governed state/category.

## Enforcement Ownership

This workstream does not add a new verifier. Enforcement remains with existing owners:

- `frontend/styles.css` for semantic token implementation;
- `scripts/verify_ui_style.py` for page-local style drift already covered by the style baseline;
- `scripts/verify_ui_reuse.py` for shared-component reuse boundaries;
- `scripts/verify_dark_mode_standard.py` for dark-mode authority;
- existing Hero verifier and Hero contract tests for Hero copy/geometry ownership;
- existing design contract tests under `tests/contracts/design/` for documentation/component authority;
- governed Visual QA for rendered light/dark/responsive evidence.

Future enforcement is extended through these existing owners when a rule is objectively machine-checkable. Do not create a one-off validation script for this matrix.

## Change Rule

A foundation change is valid only when it updates the current global/detail authority and the shared implementation owner together. Domain pages consume the result; they do not fork it.

A new compact-density or presentation exception requires a semantic need, reusable ownership, light/dark and responsive behavior, accessibility behavior, extension of an existing verifier/contract when practical, and review through the normal KAORI flow.

## #607 Completion Boundary

#607 is complete when this matrix is the discoverable current foundation/content-density decision registry, the existing detailed authorities remain intact, and contract coverage proves the registry is linked from the canonical design entry points.
