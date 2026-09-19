# Structured Entry Editor

## Purpose

`components/structured_entry_editor.html` owns responsive geometry for repeatable key/value or key/type/value editors used by Kubernetes operations.

## Supported modes

- ConfigMap text entry;
- ConfigMap binary entry;
- Secret sensitive key/value entry;
- future file-backed or schema-driven operational entries.

## Rules

- Labels use 12 px semibold typography.
- Normal controls use a 40 px minimum height and 14 px values.
- Key inputs use proportional typography.
- Raw configuration, encoded binary data, commands, and code-like payloads may use monospace.
- Sensitive values use protected inputs with an explicit show/hide control.
- Validation errors appear beneath the affected field.
- Rows reflow vertically on narrow viewports and must not create page-level horizontal scrolling.
- Add and remove actions use shared 40 px button geometry.
- The editor does not own mutation submission or server validation.
