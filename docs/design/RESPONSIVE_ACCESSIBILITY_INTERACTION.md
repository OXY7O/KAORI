# KAORI Responsive, Accessibility, and Interaction Matrix

**Parent authority:** #572  
**Workstream:** #608  
**Scope:** Responsive, accessibility, state, HTMX, overlay, and interaction decision ownership only

## Purpose

This document is the Design System v2 decision matrix for adaptive composition, accessibility behavior, interaction feedback, HTMX ownership, overlays, state presentation, forms/filters, and first-run behavior.

It consolidates existing KAORI authorities and production behavior. It does not create a parallel frontend framework, page-local state model, or second accessibility system.

`KAORI_DESIGN_SYSTEM.md` remains the global visual and interaction authority. Detailed component documents and shared implementations remain normative for their owning surfaces.

## Authority Boundary

| Concern | Current authority / owner | Enforcement / evidence |
| --- | --- | --- |
| Canonical viewports | `tests/ui/conftest.py::CANONICAL_VIEWPORTS` | `KAORI_VISUAL_QA.md`, browser UI suites |
| Responsive composition | `components/RESPONSIVE_AND_HTMX.md` + owning shared component | responsive shell and representative interaction browser tests |
| Accessibility baseline | `components/ACCESSIBILITY.md` | contract tests + `tests/ui/test_accessibility_disclosures.py` |
| Overlay selection | `components/MODAL_DRAWER.md` | shared modal/drawer implementations + browser tests |
| Resource detail modal/drawer | `components/resource_detail_modal.html` + `app/static/js/detail_rows.js` | representative interaction/browser evidence |
| Destructive confirmation | `components/destructive_confirmation_modal.html` + `destructive_confirmation_modal.js` | shared interaction contract |
| Generic side drawer | `components/side_drawer.html` | gap hardened by #614 |
| Loading / refreshing | `components/LOADING.md` + shared loading components | same-region `hx-indicator` ownership |
| Empty / blocked | `components/EMPTY_ERROR_STATE.md` + shared state components | empty-state contracts |
| Persisted action feedback | `components/OPERATIONAL_ACTION_FEEDBACK.md` | shared toast + Activity Audit ownership |
| Forms / filters | `components/FORM.md`, table/filter shared primitives | filter layout contract tests |
| Visual/theme parity | `KAORI_VISUAL_QA.md` | canonical viewport × light/dark evidence |
| Reduced motion | shared CSS/JS owners | current gap bounded by #613 |

Historical lock/audit documents remain evidence, not competing current authority.

## Canonical Viewport Matrix

The executable authority is `tests/ui/conftest.py`. Tests and documentation must reference this matrix instead of copying breakpoint values into page-local suites.

| Name | Width | Height | Intent |
| --- | ---: | ---: | --- |
| large-desktop | 1440 | 900 | large desktop |
| laptop | 1280 | 800 | standard laptop |
| compact-laptop | 1024 | 768 | compact laptop |
| tablet | 768 | 1024 | tablet |
| mobile | 390 | 844 | phone |
| small-mobile | 360 | 800 | small phone |

Real-device UAT is additional evidence. A physical device name is not a CSS contract.

## Responsive Composition Matrix

| Surface / concern | Wide behavior | Adaptive behavior |
| --- | --- | --- |
| Application shell | Persistent desktop shell/navigation | tablet/phone navigation uses shared mobile overlay ownership |
| Hero | Full profile composition with documented context/action layout | recompose or stack; preserve page identity and primary action |
| Actions | Horizontal groups where space permits | wrap/stack without hiding the primary action |
| Filters | Shared full-width wrapping geometry | stack/wrap without page-level horizontal overflow |
| Tables | Preserve primary identity/state/action columns | lower-priority columns may hide; required evidence may scroll horizontally inside the table surface |
| Cards / grids | multi-column only when content remains readable | collapse to fewer columns or one column |
| Modal | bounded centered dialog | use dynamic viewport constraints and preserve reachable actions |
| Side drawer | bounded right-side overlay | shared owner controls full-width/adaptive behavior |
| Notification deck | bounded utility overlay | full-width on phone with tabs/actions preserved |

Smaller viewports **recompose; they do not merely shrink**. Device-specific page-local CSS is prohibited when the shared responsive owner can express the requirement.

## Accessibility Matrix

| Requirement | Contract |
| --- | --- |
| Visible focus | Every interactive control exposes a visible focus state through the owning shared component. |
| Meaningful label | Controls have visible text or an accessible name. Icon-only actions require `aria-label` and/or `title` according to the component contract. |
| Keyboard access | Interactive behavior must be reachable without pointer input. |
| Dialog semantics | Dialog overlays expose `role="dialog"` or native dialog semantics, an accessible name, and modal semantics where applicable. |
| Focus entry | Opening an overlay moves focus into the interactive surface or its first meaningful control. |
| Focus containment | Modal interactions contain Tab/Shift+Tab traversal while open. Generic side-drawer parity is bounded by #614. |
| Focus return | Closing a modal/disclosure returns focus to the logical opener. Generic side-drawer parity is bounded by #614. |
| Escape | Dismissible menus/dialogs/drawers use the shared Escape behavior. |
| Dynamic feedback | Loading, search feedback, and toast state use `role` / `aria-live` / `aria-atomic` where the shared owner requires announcement. |
| Busy state | Async regions expose `aria-busy` when the owning component can accurately represent pending work. |
| Current/sort state | Pagination uses `aria-current`; sortable headers use `aria-sort`. |
| Color semantics | State never relies on color alone. |
| Theme parity | Focus, text, semantic state, and contrast remain usable in light and dark modes. |
| Touch/control geometry | Page-level form/action controls retain the existing 40 px minimum-height contract; compact controls remain component-owned exceptions, not a page-local density shortcut. |

Accessibility is component acceptance criteria, not a late audit phase.

## Overlay Selection and Focus Ownership

Use the least disruptive shared surface that matches the operator task.

| Intent | Surface | Ownership rule |
| --- | --- | --- |
| Inspect operational/resource detail | Drawer or registered resource-detail presentation | preserve underlying workspace context |
| Focused confirmation / destructive action | Modal | explicit confirmation; service-side guardrails remain authoritative |
| Short focused workflow requiring modal context | Modal | do not duplicate page navigation |
| Utility disclosure/menu | Application-shell disclosure owner | Escape + focus return belong to the shared controller |
| Global search | Application-shell dialog | search receives focus; focus is contained and restored |
| Inline expansion | Disclosure/expandable component | do not escalate to modal without a focus/workflow reason |

The resource-detail and destructive-confirmation implementations already demonstrate focus entry, containment, Escape behavior, and opener restoration. The canonical generic side drawer is retained, with missing parity tracked in #614 rather than patched page by page.

## HTMX Ownership Matrix

| Interaction | Required ownership |
| --- | --- |
| Filter / sort / pagination refresh | Replace only the owning data region; preserve other filter/sort/page/per-page/scope state. |
| Loading indication | `hx-indicator` points to the loading bar owned by the same partial region. |
| Form mutation | Initiating control uses shared disabled/loading ownership such as `hx-disabled-elt`; do not block the full page for a partial operation. |
| Same-page mutation result | Return the smallest complete stable workspace partial. |
| Root replacement | Use stable target ID and `outerHTML` when the root itself changes. |
| Toast feedback | Use out-of-band toast swap; do not replace the primary content target. |
| Location-changing mutation | Persist the normalized activity event first, then use `HX-Redirect` when the resulting resource location changes. |
| Detail URL state | Shared detail owner manages push/replace history; page templates do not invent another URL-state controller. |
| Background refresh | Preserve Hero, unrelated controls, and operator context. |
| Error transport | Render the owning operational feedback/error surface; do not reinterpret transport/runtime errors as empty state. |

No arbitrary sleeps, page-local request state machines, or duplicate HTMX history owners are allowed.

## Operational State Matrix

| Condition | Canonical presentation | Required behavior |
| --- | --- | --- |
| Loading | shared loading/skeleton/indicator owner | keep surrounding context stable; never fake completion |
| Refreshing | same-region loading indicator | keep current content visible where the owner supports it |
| Empty / healthy zero | shared empty state | distinguish genuine zero from failure |
| No results after filter/search | shared empty state with `No Results` semantics | retain filters and result context |
| First-run / source not registered | shared empty state with setup-required semantics | point to the legitimate setup path |
| Source registered, no snapshot | shared empty state with sync-required semantics | do not imply healthy evidence |
| Blocked prerequisite | shared blocked state | explain unavailable prerequisite and next valid action |
| Runtime / mutation error | operational feedback/error surface | never render as empty |
| Degraded dependency | preserve usable workspace + explicit degraded semantic state | do not collapse a partially usable workspace into blocked |
| Stale committed evidence | keep committed evidence visible with freshness/snapshot context | never present stale committed state as live/current |
| Partial source / coverage | explicit partial/warning semantics | aggregate must not appear fully healthy |
| Permission denied | authorization/route boundary | never masquerade as empty or missing data |

Domain services own the factual state. Shared presentation owners determine how that state is communicated.

## Form, Filter, and Search Interaction Matrix

| Concern | Contract |
| --- | --- |
| Form controls | page-level inputs/selects keep the 40 px minimum-height and visible focus contract |
| Form alignment | peer fields use shared `form_field` ownership |
| Form actions | final workflow actions use shared Form Action Bar where applicable |
| Filters | use shared wrapping geometry; do not introduce fixed page-local desktop grids |
| Search/filter changes | reset pagination to page 1 while preserving other relevant state |
| Clear filters | one shared interaction owner; no competing per-page implementation |
| Mobile filters/forms | stack or wrap without page-level horizontal overflow |
| Dynamic search feedback | expose loading/empty/error announcement semantics when results update asynchronously |

Read-only filter/search/pagination/history interactions do not create Activity Audit events because they do not mutate provider state or committed evidence.

## Feedback and Toast Matrix

Persisted operational actions use one normalized event for both user-visible feedback and durable Activity Audit evidence.

- success/failure returns the affected workspace partial;
- toast delivery is out-of-band;
- errors use assertive announcement semantics where required;
- non-error feedback uses polite status semantics;
- keyboard focus pauses auto-dismiss timers;
- the global stack limits visible toast count and deduplicates feedback IDs;
- background work remains in Activity Center unless the domain explicitly selects toast delivery for a synchronous operator result.

Toast timing/animation ownership stays in `operational_toasts.js`; templates do not create page-local timers.

## Motion and Reduced-Motion Matrix

Motion communicates state change and spatial relationship; it is not decoration.

| Motion family | Current owner | v2 rule |
| --- | --- | --- |
| Loading/progress animation | shared CSS/loading components | preserve state information; non-essential motion must honor reduced-motion |
| Toast enter/exit/countdown | `operational_toasts.js` + shared toast | preserve timing semantics; reduced visual motion must not remove feedback |
| Drawer/modal transition | shared overlay implementation | keep geometry stable; reduced-motion must not impair focus or close behavior |
| Notification progress | `frontend/styles.css` | already has explicit `prefers-reduced-motion: reduce` handling |

Current reduced-motion coverage is not yet complete across every shared motion owner. **#613** is the bounded implementation work; #608 does not add page-local patches.

## Representative Executable Evidence

Current acceptance evidence is intentionally reused rather than replaced:

- `tests/ui/conftest.py` — executable canonical viewport authority.
- `tests/ui/visual_audit.py` — shared viewport/overflow and visual-evidence assertions.
- `tests/ui/test_authenticated_responsive_shell.py` — shell adaptation and mobile navigation.
- `tests/ui/test_accessibility_disclosures.py` — disclosure/dialog focus, focus return, focus containment, validation association, and live-region behavior.
- `tests/ui/test_representative_interactions.py` — light/dark, overlay, HTMX, filter, pagination, and form interaction coverage.
- `tests/ui/test_runtime_state_responsiveness.py` — responsive first-run/readiness state evidence.
- `tests/contracts/design/test_application_shell_interaction_contract.py` — shell/HTMX ownership.
- `tests/contracts/design/test_filter_layout_standard_contract.py` — shared filter geometry.
- `tests/contracts/design/test_kaori_empty_state_standard_contract.py` — canonical empty/blocked state ownership.
- existing dark-mode, shared-style, and UI-reuse verifiers remain in force.
- `KAORI_VISUAL_QA.md` remains the human multi-viewport/light-dark review authority.

## Gap Disposition

#608 found two concrete implementation gaps and split them from this documentation workstream:

1. **#613 — Extend reduced-motion coverage across shared KAORI interaction feedback.**
2. **#614 — Harden canonical side drawer focus containment and focus return.**

These issues are implementation follow-ups. They do not justify a new frontend state framework or page-local workaround.

## Change Rule

A responsive/accessibility/interaction change must update the shared owner first and extend existing contracts/browser evidence when the behavior is machine-verifiable.

New page-local JavaScript, device-specific CSS, ad-hoc focus handling, duplicate loading state, or duplicate HTMX history ownership requires proof that no current shared owner can represent the need.

## #608 Completion Boundary

#608 is complete when this matrix is registered in the canonical design authority, canonical viewports match governed Visual QA, existing executable evidence is mapped, and uncovered implementation drift is represented by bounded follow-up issues rather than hidden inside the authority document.
