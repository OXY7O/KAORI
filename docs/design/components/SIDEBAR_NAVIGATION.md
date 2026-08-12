# KAORI Sidebar Navigation Standard v1.3

**Status:** Locked application-shell and dark-mode contract. The source templates, this document, and `scripts/verify_sidebar_navigation_standard.py` must change together.

This document is the authoritative visual, typography, spacing, hierarchy, and interaction contract for the authenticated KAORI sidebar. Sidebar navigation is an application-shell component and intentionally does **not** inherit the ordinary content typography scale unchanged.

## Why the Sidebar Has Its Own Scale

The sidebar must preserve three visible hierarchy levels inside a fixed-width navigation surface:

1. navigation section label;
2. parent menu;
3. submenu item.

Applying the content scale directly makes parent navigation too small, weakens orientation, and causes parent and child items to look equivalent. The sidebar therefore uses a compact but independently governed scale.

## Scope

This standard applies to:

- KAORI brand block;
- navigation section labels;
- top-level direct links;
- expandable parent menus;
- nested submenu links;
- active, hover, focus, expanded, and collapsed states;
- sidebar icons, chevrons, guide lines, spacing, and truncation.

It does not apply to tabs, page breadcrumbs, table navigation, pagination, or navigation controls inside content cards.

## Frame and Width

| State | Width | Contract |
|---|---:|---|
| Expanded | 250 px | Brand, section labels, parent labels, submenu, and chevrons are visible. |
| Collapsed | 78 px | Parent icons remain centered; text, section labels, submenu, and chevrons are hidden. |

The sidebar frame uses:

- `rounded-2xl`;
- `surface-sidebar`;
- restrained outline and elevation;
- vertical scrolling only inside the navigation region;
- stable width transitions without changing the main content hierarchy.

Collapsed mode is an icon rail, not a compressed text sidebar. Parent labels must never be reduced to fit the collapsed width.

## Typography Scale

The sidebar typography scale is frozen independently from content typography.

| Role | Size | Weight | Casing | Line height |
|---|---:|---|---|---|
| Product name | 14 px | Extra-bold / strong brand emphasis | Official `KAORI` casing | 20 px |
| Product descriptor | 12 px | Medium | Title Case | 16 px |
| Navigation section label | 12 px | Extra-bold | Uppercase | 16 px |
| Parent menu label | 16 px | Semibold | Title Case | 24 px |
| Submenu label | 14 px | Regular or medium | Title Case | 20 px |

### Mandatory hierarchy

Parent menu labels must remain visually stronger than submenu labels:

```text
Parent menu: 16 px semibold
Submenu:     14 px regular/medium
```

Do not shrink parent labels to `text-sm` or `text-xs` merely to make all application text use the same class. The semantic role is different.

### Casing exceptions

The sidebar may use deliberate uppercase and tracking for short section labels such as:

```text
MAIN
KUBERNETES
INSIGHTS & REPORTING
PLATFORM EXTENSIONS
ADMINISTRATION
```

This is a shell-navigation exception. Parent menu and submenu labels remain Title Case and must not use CSS `capitalize`.

Technical product names keep their official casing:

```text
K8s Inventory
Prometheus
Alertmanager
GitOps
OAuth
LDAP
```

## Brand Block

The brand block contains:

```text
[KAORI Logo] KAORI
             Infrastructure Operations
```

Contract:

- logo surface: 44 × 44 px;
- product name: strong brand emphasis, not ordinary card-title styling;
- descriptor: 12 px medium and muted;
- brand block remains vertically centered;
- collapsed mode shows only the logo, centered;
- no alternate text abbreviation is shown in collapsed mode.

## Navigation Sections

Section labels provide grouping, not navigation.

Contract:

- visible only in expanded mode;
- 12 px extra-bold uppercase;
- restrained tracking;
- low-contrast inverse text;
- 12 px horizontal inset relative to the sidebar frame;
- not interactive and not focusable;
- section groups use a larger vertical gap than links inside one group.

## Parent Menu

Parent navigation represents a primary functional domain such as Inventory, Analytics, Reports, Integrations, or Settings.

### Geometry

- minimum height: 44 px;
- horizontal padding: 10 px;
- vertical padding: 8 px;
- radius: 8 px (`rounded-lg`);
- icon surface: 32 × 32 px;
- icon: 16 × 16 px;
- icon-to-label gap: 10 px;
- label: 16 px semibold;
- chevron: 16 × 16 px;
- full-width click target in expanded mode.

### Direct parent links

A direct top-level link uses the same geometry and typography as an expandable parent menu. The visual hierarchy must not change merely because it has no submenu.

### Default state

Canonical classes:

```text
sidebar-item-idle
sidebar-item-idle-icon
```

- muted inverse foreground owned by the sidebar token;
- transparent background;
- icon surface uses a restrained translucent background;
- no provider-specific color.

### Hover state

- subtle white/translucent surface;
- foreground becomes white;
- icon surface becomes slightly stronger;
- pointer cursor;
- no scale animation.

### Active state

Canonical classes:

```text
sidebar-parent-active
sidebar-parent-active-icon
```

- light mode uses a solid KAORI Violet surface;
- dark mode keeps the active Violet surface without a separate left-edge accent;
- label remains white and the dark-mode icon uses Accent Violet;
- dark mode does not use a large glow or CTA-like elevation;
- active parent remains visually dominant over its active submenu;
- active state is determined from the owned endpoint set, not only the exact index route.

### Expanded state

- chevron rotates to indicate disclosure;
- submenu appears below the parent;
- parent may remain active when any owned child route is active.

### Collapsed interaction

When a collapsed parent with children is activated:

1. expand the sidebar;
2. keep the selected parent open;
3. reveal its submenu;
4. do not navigate to an arbitrary child automatically.

Each parent icon must retain `title` and `aria-label` so collapsed navigation remains understandable.

## Submenu

Submenu links are secondary navigation and must not compete with their parent.

### Geometry

- left offset: 24 px from the parent content line;
- guide line: subtle vertical border;
- inner left padding: 12 px;
- row horizontal padding: 10 px;
- row vertical padding: 6 px;
- radius: 8 px;
- icon: 14 px;
- indicator dot: 6 px;
- label: 14 px with 20 px line height;
- item gap: 8 px between dot, icon, and text composition.

### Default state

- muted inverse foreground;
- transparent background;
- subdued dot and icon;
- no bold weight by default.

### Hover state

- subtle translucent surface;
- foreground becomes white;
- dot becomes more visible;
- no solid Violet fill.

### Active state

- restrained translucent surface;
- accent-violet text, icon, and dot;
- active submenu remains visually subordinate to the active parent;
- do not use the same solid Violet fill as the parent.

## Icons

Sidebar icon sizes are shell-specific:

| Role | Size |
|---|---:|
| Brand logo | 44 px |
| Parent icon surface | 32 px |
| Parent icon | 16 px |
| Parent chevron | 16 px |
| Submenu icon | 14 px |
| Submenu indicator dot | 6 px |

Rules:

- each parent requires a meaningful, stable icon;
- submenu icons are permitted where they improve scanning;
- icons must remain consistent when state changes;
- active state changes color/surface, not the icon glyph;
- avoid mixing outline families or arbitrary sizes.

## Spacing and Density

Sidebar density is compact but not compressed.

```text
Sidebar outer padding        12 px
Brand-to-navigation gap      8–12 px
Section-to-section gap       16 px
Links inside one section      4 px
Parent-to-submenu gap         4 px
Submenu item gap              4 px
```

Do not reduce parent row height to match submenu rows. The height difference is part of the navigation hierarchy.

## Text Overflow

- parent and submenu labels use a single line;
- use `truncate whitespace-nowrap`;
- do not wrap labels to two lines;
- fix clipping by adjusting width, gap, padding, or owned label wording—not by reducing the parent font below 12 px;
- labels should be concise and recognizable.

## Color and Effects

The sidebar uses inverse shell colors rather than ordinary content-surface colors.

- Default text: muted inverse foreground.
- Hover text: white.
- Active parent: solid KAORI Violet in light mode; translucent Violet plus a left accent in dark mode.
- Active child: accent Violet on a restrained translucent surface.
- Guide lines and inactive dots: low-contrast white.
- Shadows are reserved for the active parent and the sidebar frame.
- Navigation items do not use gradients, semantic status colors, or CRUD colors.
- Dark-mode values are owned by `components/DARK_MODE.md`; menu templates do not add local dark classes.

## Accessibility

- `nav` remains the semantic navigation container.
- expandable parents use native `details` and `summary` or an equivalent accessible disclosure pattern;
- summary controls expose a meaningful accessible name;
- collapsed parent icons retain `title` and `aria-label`;
- focus-visible treatment must remain visible on the dark sidebar surface;
- active navigation is indicated by more than color through surface, foreground, and route ownership;
- labels are never removed from the accessibility tree merely because the sidebar is collapsed.

## Responsive and Collapse Rules

- expanded desktop width is 250 px;
- collapsed desktop width is 78 px;
- collapsed mode hides textual navigation rather than reducing its typography;
- submenu is not rendered as an icon-only nested rail;
- mobile behavior may use an overlay drawer while preserving the same parent/submenu hierarchy;
- route state and expanded menu state must remain stable after HTMX updates to the main content region.

## Canonical Information Architecture

The top-level order is locked. New modules must be placed in the existing domain group unless an approved information-architecture change updates this document and the verifier in the same commit.

```text
MAIN
├── Welcome
└── Dashboards

KUBERNETES
├── K8s Inventory
├── K8s Operations
└── K8s Governance

STORAGE
└── Object Storage
    ├── Overview
    ├── Systems
    └── Buckets

INSIGHTS & REPORTING
├── K8s Analytics
├── Intelligence
└── Reports

PLATFORM EXTENSIONS
└── Integrations

PLATFORM OPERATIONS
└── Platform Operations

ADMINISTRATION
├── Access
└── Settings
```

v1.3 adds the approved **Storage** section. `Object Storage` is a provider-neutral inventory parent; vendor connectors such as MinIO remain under Integrations and must not become sidebar inventory parents. The first locked children are Overview, Systems, and Buckets.

Rules for adding navigation:

1. Add a child route to an existing parent when it belongs to the same operational domain.
2. Add a new parent only when the module owns a distinct domain and cannot be represented by an existing parent.
3. Do not create a new section label for one feature. A new section requires an explicit information-architecture decision.
4. Permission checks remain in `sidebar.html`; route ownership and active-state logic remain in the owning `*_menu.html`.
5. Every expandable parent requires `title`, `aria-label`, collapsed-sidebar expansion behavior, one stable Lucide icon, and an owned endpoint set.
6. Every submenu link uses the standard dot, 14 px icon, single-line truncated label, and subordinate active state.

## Enforcement and Change Control

The sidebar is considered locked only when documentation, implementation, dark-mode tokens, and enforcement agree:

```text
Documentation  docs/design/components/SIDEBAR_NAVIGATION.md
Implementation app/templates/components/navigation/sidebar.html
               app/templates/components/navigation/*_menu.html
Theme contract docs/design/components/DARK_MODE.md
Quality gate   scripts/verify_sidebar_navigation_standard.py
               tests/contracts/design/test_sidebar_navigation_standard_contract.py
```

Any sidebar change must update the contract deliberately. Never weaken or delete an assertion merely to make a local menu variant pass. A legitimate standard change must include rationale, documentation, implementation updates, regression tests, and a design-system version increment.

### New-parent checklist

- assign the parent to one canonical section;
- add the permission boundary in `sidebar.html`;
- create one `*_menu.html` owner;
- reuse 44 px parent geometry and 32 px icon surface;
- use `text-base font-semibold leading-6`;
- add `title`, `aria-label`, and collapsed expansion behavior;
- use a stable endpoint-family active rule;
- keep child links at `text-sm leading-5`;
- run `python scripts/verify_sidebar_navigation_standard.py`;
- run the design contract tests.

## Prohibited Patterns

Do not:

- apply ordinary content typography wholesale to sidebar navigation;
- make parent and submenu labels the same size and weight;
- shrink parent labels below 16 px to solve clipping;
- use `font-bold` or extra-bold on every navigation item;
- use solid Violet for active submenu links;
- use provider-specific colors in navigation;
- wrap navigation labels;
- show submenu text in the 78 px collapsed rail;
- place page actions, status labels, or operational metrics inside navigation rows;
- duplicate a domain in multiple parent groups without an explicit information-architecture decision.

## Implementation Reference

Current reference templates:

```text
app/templates/components/navigation/sidebar.html
app/templates/components/navigation/*_menu.html
```

The current implementation establishes the baseline classes:

```text
Parent:  min-h-11 rounded-lg px-2.5 py-2 text-base font-semibold leading-6
Child:   rounded-lg px-2.5 py-1.5 text-sm leading-5
Section: text-xs font-extrabold uppercase tracking-widest
```

These Tailwind tokens are the canonical sidebar scale. The earlier 12/11 px markdown baseline and the 15/13 px visual-guide draft are superseded by this v1.1 contract.

## Review Checklist

Before accepting a sidebar change, verify:

- parent remains 16 px semibold (`text-base leading-6`);
- submenu remains 14 px (`text-sm leading-5`) and visually subordinate;
- section label remains compact uppercase metadata;
- collapsed mode hides text instead of shrinking it;
- active parent and active child use different emphasis levels;
- long labels truncate without clipping their icon;
- submenu guide and spacing remain visible;
- icon, hover, focus, disclosure, and endpoint ownership states work;
- no global content typography migration has altered sidebar hierarchy.
