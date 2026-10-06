# KAORI Design System v2 Authority Audit — 2026-09-24

**Parent authority:** #572  
**Workstream:** #605  
**Scope:** Documentation and verification ownership inventory only  
**Source reviewed:** `kaori/staging@eca4586e690195b30b6d9a54bccfda67d654dea2`

## Outcome

KAORI already has a mature reusable UI authority. Design System v2 should therefore be a consolidation and explicit-selection program, not a clean-sheet redesign.

The review found three categories:

- **Retain** — current authority is clear and reusable.
- **Consolidate** — current behavior/contract exists, but navigation between authorities is fragmented or the selection rule is implicit.
- **Gap workstream** — #572 requires an explicit matrix/registry not yet represented as one coherent current authority.

No broad visual migration is authorized by this audit.

## Documentation Authority

| Concern | Current authority | Disposition |
| --- | --- | --- |
| Global visual/interaction rules | `KAORI_DESIGN_SYSTEM.md` | **Retain** as canonical global authority |
| Practical component/page selection | `KAORI_STYLING_GUIDE.md` | **Retain** |
| Compact entry point | `DESIGN_SYSTEM.md` | **Consolidate** into authority index; do not treat as a second version |
| Design documentation navigation | `README.md` | **Consolidate** around the same authority order |
| Shared component contracts | `components/*.md` | **Retain** |
| Reusable page patterns | `patterns/*.md` | **Retain** |
| Domain-specific UI behavior | owning module docs | **Retain** |
| Visual evidence/UAT | `KAORI_VISUAL_QA.md` | **Retain** |
| Historical lock/audit files | `KAORI_*_LOCK_*.md`, `audits/*.md` | **Retain as evidence**, never newer global authority |
| Engineering/release review index | `docs/standards/KAORI_ENGINEERING_STANDARD_V1.md` | **Retain** outside design-specific ownership |

## Foundation Coverage

| #572 area | Existing authority | Status / next owner |
| --- | --- | --- |
| Brand / Violet identity | `KAORI_DESIGN_SYSTEM.md`, `COLOR_AND_SEMANTIC.md` | Retain; matrix consolidation in #607 |
| Semantic colors / dark mode | `COLOR_AND_SEMANTIC.md`, `DARK_MODE.md` | Retain; #607 indexes light/dark role matrix |
| Typography | `TYPOGRAPHY.md`, Hero-specific rules in `HERO.md` | Retain; #607 reconciles role/text-budget matrix |
| Copy density | Hero/styling/component contracts and existing copy audits | Consolidate in #607 |
| Spacing / density | `SPACING.md`, global design contract | Retain; #607 |
| Shape / borders / elevation | `KAORI_DESIGN_SYSTEM.md`, component contracts | Consolidate in #607 |
| Iconography | `ICONS.md` | Retain; #607 |
| Technical value presentation | `TECHNICAL_VALUE.md`, `TECHNICAL_METADATA_COLLECTION.md` | Retain; #607 |
| Responsive baseline | `RESPONSIVE_AND_HTMX.md`, `KAORI_VISUAL_QA.md` | Retain; #608 |
| Accessibility | `ACCESSIBILITY.md` plus component contracts | Retain; #608 |
| Motion / interaction feedback | component contracts + application shell behavior | Partial index; #608 |

## Application and Component Coverage

| Family | Existing authority | Disposition |
| --- | --- | --- |
| Application shell / sidebar / navbar | `SIDEBAR_NAVIGATION.md`, `NAVBAR.md`, global design contract | Retain |
| Hero | `HERO.md`, `ANALYTICS_HERO.md` | Retain |
| Tabs/navigation | `TAB_STYLES.md`, `WORKSPACE_TABS.md`, `FRAMED_WORKSPACE_TABS.md`, `SEGMENTED_TABS.md`, `CONTENT_TABS.md` | Consolidate selection matrix in #606 |
| Cards/content blocks | component catalog including Operational, Summary, Context, Guide, Related Page, Link cards | Retain; selection map in #606/#609 |
| Tables/labels | `TABLE_AND_LABEL.md`, pagination and filter standards | Retain |
| Buttons/actions | `BUTTON.md`, section-header/action and operational-feedback contracts | Retain |
| Forms | `FORM.md`, `FORM_FIELD.md`, `FORM_ACTION_BAR.md`, `FORM_WITH_CONTEXT_RAIL.md` | Retain |
| Filters/search/toolbars | styling/component conventions, global search contracts | Partial index; #608 |
| Modals/drawers | `MODAL_DRAWER.md`, `SIDE_DRAWER.md`, `RESOURCE_DETAIL_MODAL.md` | Retain; decision matrix in #608 |
| State/feedback | `EMPTY_ERROR_STATE.md`, `LOADING.md`, operational callout/action feedback | Retain; unified state matrix in #608 |
| Analytics/visualization | analytics component family + `VISUALIZATION_WORKSPACE.md` | Retain |

## Page Composition Coverage

Current reusable patterns are strongest for Inventory, Operational pages, Dashboard, Welcome, Kubernetes operations, and Object Storage inventory.

The missing global authority is **not another set of templates**. The missing authority is one explicit registry that maps an intended page to a known archetype and approved composition roles.

Disposition: **#606** owns the archetype and tab/navigation decision registry. Existing pattern documents remain the detailed implementation authorities.

## Reference and Enforcement Coverage

Current enforcement already exists and must be extended rather than replaced:

- `scripts/verify_ui_reuse.py`
- `scripts/verify_ui_style.py`
- existing component/design contract tests under `tests/contracts/design/`
- architecture/code-health checks where ownership boundaries apply
- governed Playwright Visual QA in `tests/ui/`
- `KAORI_VISUAL_QA.md` human review/UAT authority

Disposition: **#609** owns the reference implementation and enforcement coverage map.

## Historical Lock Files

The numerous `KAORI_*_LOCK_V*.md` documents are retained because they record accepted decisions and lineage. They are not independent current global standards.

Rule:

```text
Current global/component/pattern authority
→ current domain specification
→ historical lock/audit evidence
```

A historical lock may justify why a rule exists, but it must not override a newer shared component/global contract.

## Identified Concrete Gaps

This audit found four bounded gaps already represented by #572 children:

1. **Page archetype and navigation/tab selection registry** — #606.
2. **One consolidated foundation/content-density matrix** — #607.
3. **One responsive/accessibility/state/interaction matrix** — #608.
4. **One production-reference + enforcement coverage map and extension policy** — #609.

No fifth component family, new CSS token framework, or broad page migration is justified by this audit.

## Reference Authorities Already Strong Enough to Reuse

Representative production-grade authorities include:

- Hero: `components/HERO.md` + shared page Hero implementation.
- Table/labels: `components/TABLE_AND_LABEL.md` + shared table-label components.
- Tabs: registered tab-style component family.
- Inventory: Kubernetes inventory patterns and shared detail components.
- Dashboard: `patterns/OPERATIONAL_DASHBOARD.md`.
- Analytics: analysis surface and visualization component family.
- Integrations: Integration Manage Workspace.
- Operational flows: shared workflow/action-feedback components.
- Responsive/visual evidence: `KAORI_VISUAL_QA.md` canonical viewport matrix.

#609 will record exact production surface references rather than introducing demo pages.

## Verification Ownership

#605 changes only documentation authority/indexing and extends the existing design contract test. It does not add a new validation script.

Expected validation:

- existing design contract tests;
- existing documentation/style checks selected by Developer Check;
- no runtime/UI visual baseline change;
- fresh staging integration evidence after merge.

## Manual Project Metadata

The connected GitHub tooling cannot set Project custom fields or native Parent/Sub-issue relationships.

Required manual relationship:

- #572 parent
  - #605
  - #606
  - #607
  - #608
  - #609

No Milestone is required for these workstreams while no bounded release target has been selected.
