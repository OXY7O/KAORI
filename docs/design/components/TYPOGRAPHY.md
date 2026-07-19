# KAORI Typography Standard

Status: Global design-system standard
Applies to: Flask/Jinja/HTMX application surfaces, including heroes, content cards, tables, forms, filters, drawers, modals, toasts, reports UI, and empty/error states.

## 1. Core principle

KAORI uses one application font family and a limited, repeatable type scale. Typography must communicate hierarchy before decoration. Font size, weight, line height, color, casing, and spacing are part of one semantic contract and must not be chosen independently per page.

Use the lightest visual treatment that still makes the content hierarchy clear. Do not make every heading bold, large, violet, or uppercase.

## 2. Font family

Use the application sans-serif font inherited from the global layout and Tailwind configuration.

Rules:

- Do not declare a local font family inside individual templates.
- Do not mix font families between modules.
- Use monospace only for technical values that benefit from fixed-width glyphs, such as hashes, identifiers, paths, commands, ports, or code fragments.
- Monospace values must remain secondary to the surrounding content hierarchy.

## 3. Casing contract

### 3.1 Title Case is the default for visible content headings

Use Title Case for:

- hero titles;
- section and card titles;
- table-block titles;
- modal and drawer titles;
- form-section titles;
- filter-group titles;
- table column headers;
- tabs;
- visible button labels;
- short expandable-section titles.

Examples:

- `Infrastructure Integrations`
- `Runtime Validation`
- `Resource Inventory`
- `Last Observed`
- `Save Readiness`

### 3.2 Sentence case remains valid for narrative content

Use sentence case for:

- descriptions;
- helper text;
- explanatory paragraphs;
- empty and error messages;
- toast body content;
- inline guidance;
- long operational explanations.

Examples:

- `Registered infrastructure targets and their current runtime state.`
- `No pods match the current filters.`

### 3.3 Capitalize or uppercase only for intentional design cases

Limited uppercase or capitalize treatment is allowed only where already established by the design and where it improves scanning, such as:

- compact hero eyebrow labels, for example `INTEGRATIONS`;
- short domain/category markers;
- acronyms and product names, for example `KAORI`, `SSO`, `LDAP`, `TLS`, `CPU`, `API`;
- provider or protocol names whose official casing must be preserved;
- compact metadata where the component specification explicitly requires uppercase.

Do not apply `uppercase`, `capitalize`, or expanded tracking to ordinary content headings or table headers merely for decoration.

### 3.4 Preserve technical and proper-name casing

Do not rewrite technical values into Title Case.

Examples that retain their source casing:

- `kube-system`
- `prometheus-v3`
- `api-gateway-7f8d9`
- `v1beta1`
- `sha256`
- user email addresses;
- URLs, file paths, commands, metric names, Kubernetes object names, and identifiers.

## 4. Approved typography hierarchy

The following hierarchy summarizes the scale already implemented across KAORI and becomes the global reference.

| Semantic role | Tailwind baseline | Approx. size | Weight | Default casing | Typical color |
|---|---:|---:|---:|---|---|
| Hero title | `text-2xl` to `text-3xl` | 24–30 px | `font-semibold` or `font-bold` only when required by the hero composition | Title Case | Primary content |
| Page or major section title | `text-xl` to `text-2xl` | 20–24 px | `font-semibold` | Title Case | Primary content |
| Card / table-block / modal title | `text-base` to `text-lg` | 16–18 px | `font-semibold` | Title Case | Primary content |
| Subsection / expandable title | `text-sm` to `text-base` | 14–16 px | `font-semibold` or `font-medium` | Title Case | Primary content |
| Primary resource/title cell | `text-sm` | 14 px | `font-semibold` | Preserve resource casing | Primary content |
| Ordinary content/body | `text-sm` | 14 px | `font-normal` or `font-medium` where emphasis is needed | Sentence case | Primary/secondary content |
| Description/helper/supporting text | `text-xs` to `text-sm` | 12–14 px | `font-normal` | Sentence case | Muted/secondary content |
| Table column header | `text-xs` | 12 px | `font-semibold` | Title Case | Muted content |
| Filter label / form label | `text-xs` | 12 px | `font-semibold` | Title Case | Secondary content |
| Table action / compact control | `text-xs` | 12 px | `font-medium` | Title Case, maximum two words where practical | Secondary content |
| Compact semantic label | dedicated label contract | 10 px | `font-semibold` | Short status/category text | Semantic color |
| Fine metadata | `text-xs` | 12 px | `font-normal` | Preserve value casing | Muted content |
| Technical code/value | `text-xs` to `text-sm` plus monospace | 12–14 px | `font-normal` or `font-medium` | Preserve exact casing | Primary/secondary content |

## 5. Heading treatment

A visible title normally combines:

- Title Case;
- primary content color;
- semibold weight;
- compact line height;
- no decorative tracking;
- no forced uppercase.

The title effect must be consistent for the same semantic level. Do not make one card title bold, another violet, and another uppercase when they perform the same role.

### 5.1 Bold versus semibold

Use `font-semibold` as the normal heading weight.

Use `font-bold` only when:

- the hero design requires stronger emphasis;
- a high-level page title must visually separate from a dense surrounding layout;
- a number/KPI requires deliberate emphasis;
- the component specification explicitly defines bold.

Do not use bold as a substitute for hierarchy or spacing.

### 5.2 Violet text

Violet is an interaction and brand accent, not the default heading color.

Use Violet text for:

- active navigation or selected state;
- links and interactive hover/focus states;
- meaningful branded emphasis;
- active sort indicators;
- intentionally highlighted metadata.

Ordinary content titles use the primary content color.

## 6. Content typography rules

- Ordinary content defaults to `text-sm`.
- Supporting text defaults to `text-xs` or `text-sm` depending on available space and reading importance.
- Do not use arbitrary local sizes such as `text-[13px]`, `text-[15px]`, or `text-[17px]` unless a documented component exception exists.
- Do not mix `font-bold`, `font-semibold`, and `font-medium` randomly inside the same semantic level.
- Long descriptions use comfortable line height and remain sentence case.
- Short labels and headings should not end with punctuation unless grammatically required.
- Avoid all-caps paragraphs and long all-caps labels.

## 7. Table typography alignment

The table-specific hierarchy remains:

- column header: 12 px semibold;
- primary resource title: 14 px semibold;
- ordinary value: 14 px regular/medium;
- supporting context: 12 px muted;
- semantic label: 10 px semibold;
- compact action: 12 px medium.

A two-line title cell may have a larger icon container, but the text hierarchy does not change.

Not every cell requires an icon or label. Use text-only values where that is clearer and quieter.

## 8. Forms and filters

- Form and filter labels use Title Case, 12 px semibold.
- Input values use 14 px regular.
- Placeholder and helper text use 12–14 px muted.
- Validation messages use 12–14 px and semantic color.
- Do not use uppercase labels for ordinary form fields.
- Preserve official casing for provider names and technical field values.

## 9. Buttons and controls

- Visible button labels use Title Case.
- Compact table actions generally use 12 px medium and no more than two words where practical.
- Page-level actions may use 13–14 px medium/semibold according to the button component.
- Button hierarchy is expressed through component treatment, not through inconsistent font sizing.
- Destructive actions retain the same font geometry as ordinary actions; semantic color provides the distinction.

## 10. Labels, badges, and status text

Use the compact label component only for status, severity, state, category, or concise metadata tokens.

- 10 px semibold;
- `rounded-md`;
- minimum height 24 px;
- icon 12 px when useful;
- concise wording;
- semantic color plus text/icon, never color alone.

Do not convert ordinary values such as versions, counts, timestamps, namespaces, or names into labels without a semantic reason.

## 11. Responsive typography

Typography may step down by one documented level on narrow screens, but semantic hierarchy must remain intact.

- Do not shrink body content below 12 px.
- Do not shrink compact semantic labels below 10 px.
- Avoid wrapping short action labels where possible.
- Allow long titles to wrap naturally or truncate when the component contract requires one line.
- Supporting context can be hidden only when the primary value remains understandable.

## 12. Exceptions

A deviation is valid only when at least one condition applies:

- official brand/provider casing;
- technical identifier preservation;
- code or metric readability;
- dense visualization or chart annotation;
- legally required wording;
- an explicitly documented component-specific contract.

Document recurring exceptions instead of repeatedly introducing local utility combinations.

## 13. Implementation guardrails

New or modified templates should avoid:

- arbitrary font sizes;
- forced uppercase on ordinary headings;
- expanded tracking on ordinary headings;
- local font-family declarations;
- Violet as the default color for every title;
- bold on every title level;
- inconsistent casing for equivalent components.

Preferred shared sources of truth:

- global layout and Tailwind theme for font family;
- Hero component standard;
- Button component standard;
- Table and Label component standard;
- this Typography standard for content hierarchy and casing.

## 14. Review checklist

Before accepting a new page or component, verify:

1. Is every visible heading using the correct semantic level?
2. Is Title Case used for headings and controls, while descriptions remain sentence case?
3. Are technical values preserving their exact casing?
4. Is semibold used as the default title weight instead of arbitrary bold?
5. Are only approved sizes used?
6. Are equivalent components visually identical across pages?
7. Is Violet reserved for interaction, state, and intentional emphasis?
8. Is monospace limited to technical values?
9. Does the hierarchy remain readable on mobile?
10. Has any recurring exception been documented?

## Control Labels and Compact Card Titles

Human-readable UI control labels and compact card titles use **Title Case**, including:

- Search and filter field labels, such as `Search Instance`.
- Metric or posture card titles, such as `Binding, Capability, and Runtime Aware`.
- Short authority or ownership statements used as card titles, such as `Alertmanager Remains Authoritative`.

Sentence case remains correct for explanatory prose, helper text, descriptions, error details, and complete sentences. Technical identifiers preserve their canonical casing.

## Integrations Semantic Label Contract

All user-facing semantic labels inside Integrations Overview, Kubernetes, Prometheus, and Alertmanager use Title Case. This includes headings, form labels, filter labels, table headers, compact information titles, and Info Flow titles.

Examples:

- `Instance Name`
- `Connection Type`
- `Search Instance`
- `Runtime and Capability State`
- `Provider / Instance`
- `Last Observed`
- `Alertmanager Registration Flow`

Descriptions, helper text, placeholders, warnings, and operational explanations remain sentence case. Technical identifiers and canonical product or protocol names retain their original casing and must not be transformed mechanically.
