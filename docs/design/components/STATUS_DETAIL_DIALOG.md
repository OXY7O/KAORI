# KAORI Status Detail Dialog Standard

## Purpose

`components/status_detail_dialog.html` is the compact detail pattern for status, blocker, and eligibility explanations that are too long for a registry/table row.

The row keeps only the semantic status label plus a compact **Details** button. The explanation opens in the browser native `<dialog>` top layer through the existing global `native_dialogs.js` controller.

## Use

Use Status Detail Dialog when:

- a table status needs multi-line explanation;
- blocker/eligibility evidence would make the row too tall;
- an Info Tip would live inside an `overflow-x` table container;
- the detail is explanatory and read-only, not a mutation.

Keep normal action buttons as buttons. Do not wrap actions such as Review, Reconcile, Edit, or Decommission in this dialog pattern.

## Table contract

A dense registry row should remain:

```text
Semantic status badge + compact detail trigger
→ native dialog top layer
→ concise summary + supporting evidence
```

The dialog itself must be rendered outside the table scroll container. This avoids clipping and phantom vertical scrollbars while preserving keyboard and pointer access.

## Accessibility

- Trigger uses `aria-haspopup="dialog"` and `aria-controls`.
- Dialog uses `data-kaori-native-dialog`, `role=document` content, labelled title, and description.
- Open/close behavior is delegated to the shared `native_dialogs.js` controller.
- Escape/backdrop/close controls follow the global native-dialog behavior.

## Boundary with Info Tip

Info Tip remains the preferred compact pattern for form fields and non-scrollable contextual controls.

For table/registry status detail:

```text
short helper → Info Tip
multi-line status/blocker evidence → Status Detail Dialog
```


## Rich state explanation

When the registry state represents a governed decision such as `Blocked`, the dialog should explain more than the raw blocker string. Prefer this order when the data exists:

1. current committed snapshot;
2. governed lifecycle or decision flow;
3. concrete reasons the current state appears;
4. operator guidance that preserves provider authority.

The dialog remains read-only. It explains the state; it must not hide a mutation behind a status-detail trigger.


## Tenant registry exception

Tenant Registry, Tenant Discovery, and Allocation Budget do **not** use a repeated per-row Status Detail trigger for generic status vocabulary. Those tables keep the row to semantic labels and place shared status guidance in one `info_tip` in the block header action area. This avoids visual noise and keeps tooltip content outside the table scroll container.

Use Status Detail Dialog only when a row carries genuinely row-specific evidence that cannot be represented by the shared glossary or a normal workflow action.
