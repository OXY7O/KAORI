# KAORI Action Button Standard

## Scope

This contract applies to visible action controls that create, save, update, apply, approve, validate, replace, submit, delete, remove, revoke, archive, restore, or otherwise mutate operational state. Navigation links, tabs, icon-only utilities, pagination controls, disclosure toggles, and compact table menus may use their own component contract, but must retain accessible labels and interaction states.

## Action hierarchy

Each action group must contain no more than one visually dominant primary action.

| Role | Usage | Visual treatment |
| --- | --- | --- |
| Primary | The action that completes the main workflow | Solid KAORI Violet |
| Secondary | Supporting, reversible, preview, validation, refresh, cancel, or back action | Neutral surface with soft border |
| Destructive | Delete, revoke, purge, permanent removal, or rejection | Solid Critical semantic color |

Primary and destructive controls share the same geometry, typography, icon placement, focus behavior, and loading behavior. Destructive differs through semantic color and action icon, not through a different shape or density.

## Required anatomy

A standard action button uses this order:

```text
[Icon] Action Label
```

Requirements:

- Visible icon precedes the text.
- Label uses Title Case.
- Label describes the result or object, for example `Save Readiness`, `Update Policy`, or `Delete Connection`.
- Avoid ambiguous labels such as `Submit`, `Confirm`, or `Save` when a more specific label is available.
- Icon size: 16 px.
- Text size: 14 px, semibold.
- Control height: 40 px.
- Horizontal padding: 16 px.
- Icon-to-label gap: 8 px.
- Radius: `rounded-lg` or the shared button helper value; do not mix pill and rectangular shapes in one action group.

## Primary color contract

```text
Default   #7C3AED  Primary Bright Violet
Hover     #6D28D9  Primary Hover / Strong Violet
Active    #5B21B6  Primary Dark / Deep Violet
Text      #FFFFFF
Focus     #A78BFA  Accent Lavender
```

Canonical Tailwind intent:

```html
class="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-lg
       bg-kaori-primary px-4 text-sm font-semibold text-white
       transition-colors duration-150
       hover:bg-kaori-primary-hover active:bg-kaori-primary-dark
       focus-visible:outline-none focus-visible:ring-2
       focus-visible:ring-outline-focus focus-visible:ring-offset-2
       disabled:cursor-not-allowed disabled:opacity-60"
```

Do not use legacy blue primary controls. KAORI Violet is the only default mutation color.

## Destructive color contract

Destructive action buttons preserve the primary geometry and interaction pattern while replacing Violet with the Critical semantic palette.

Canonical labels include:

- `[Trash] Delete Connection`
- `[User X] Revoke Access`
- `[Archive] Archive Report`

A destructive button must not be presented as the dominant action outside a destructive confirmation or Lifecycle / Danger Zone context.

## Secondary contract

Secondary controls use a neutral surface, soft border, and Charcoal Plum text. Hover may use Primary Soft with Strong Violet text. Examples:

- `[Shield Check] Validate Configuration`
- `[Eye] Preview Changes`
- `[X] Cancel`
- `[Arrow Left] Back`
- `[Refresh Cw] Refresh Status`

Validation is secondary when it supports a later save or apply step. It may become primary only when validation is the page's sole completion action.

## Ordering

Horizontal action groups use:

```text
Secondary | Primary
```

Destructive confirmation groups use:

```text
Cancel | Destructive
```

The primary or destructive action is positioned at the right edge in left-to-right layouts.

## Interaction states

Every visible action button must provide:

- `cursor-pointer` when enabled.
- Darker semantic hover color.
- Deep semantic active color.
- Visible keyboard focus ring.
- Disabled opacity and `cursor-not-allowed`.
- Stable loading geometry.

Loading labels should describe progress:

```text
[Spinner] Saving…
[Spinner] Updating…
[Spinner] Validating…
```

The button width and action-group layout must not jump during HTMX or asynchronous processing.

## Icon mapping

| Action | Preferred Lucide icon |
| --- | --- |
| Save | `save` |
| Update / Refresh | `refresh-cw` |
| Create / Add | `plus` |
| Apply / Confirm | `check` |
| Approve | `circle-check` |
| Validate | `shield-check` |
| Delete | `trash-2` |
| Remove / Cancel | `x` |
| Back | `arrow-left` |
| Reveal | `eye` |
| Download | `download` |
| Upload | `upload` |
| Archive | `archive` |
| Restore | `archive-restore` |

## Exceptions

The full icon-and-text geometry is not required for:

- Icon-only controls with an accessible `aria-label` or `title`.
- Pagination controls.
- Tabs and segmented navigation.
- Disclosure toggles.
- Compact notification utilities.
- Row overflow menus.

Exceptions may not be used for a page's primary mutation action.

## Compliance checklist

- Exactly one primary action at most in an action group.
- Save, create, update, apply, approve, and equivalent completion actions use solid KAORI Violet.
- Delete, revoke, and equivalent destructive actions use the Critical semantic palette.
- Icon precedes a Title Case label.
- Height, spacing, typography, radius, and states are consistent.
- Enabled action controls show a pointer cursor.
- No legacy blue primary button remains.
- HTMX loading does not resize or move the action group.

## Dark-mode hover contrast

Secondary and validation actions must not become low-contrast Violet text on a translucent Violet surface in dark appearance. Canonical shared actions use:

```text
Default  Neutral surface and readable content text
Hover    Solid KAORI Violet with white text
Active   Deep Violet with white text
```

This rule is owned by `components/action_button.html` and the operation-specific validation wrapper. Page-local hover color bundles are not permitted.
