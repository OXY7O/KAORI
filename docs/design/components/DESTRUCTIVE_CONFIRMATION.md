# KAORI — Governed Destructive Confirmation

## Canonical component

Use `app/templates/components/destructive_confirmation_modal.html` (macro `render`) and the existing `app/static/js/destructive_confirmation_modal.js` controller. **Do not build ad-hoc confirmation modals** or add a second modal library.

A destructive action includes deleting/destroying a resource, revoking membership or credentials, retiring a Tenant Group, and comparable high-impact changes. All have an explicit human confirmation before invoking the existing permission-checked, CSRF-protected mutation endpoint.

## Preferred presentation

For actions requiring more than a brief sentence of consequence, use `presentation='governed'`:

- Responsive width: **`max-w-3xl`**, bounded by viewport padding; short-action default remains `max-w-xl`.
- Header: semantic action icon, concise operation title, **one** short action description; no duplicate status chips.
- Context: `target_label` and `scope_label` with their dynamic target/scope values, in two balanced cells.
- Consequences: `impact_items` as one full-width **vertical** list. Each entry has an icon, concise action title, and clear consequence. Never use a two-column grid with an orphan third card.
- Risk: show **one** contextual warning only when needed (`warning`). Additional `consequence` should be independent and non-duplicative; leave it empty when already covered by the impact list.
- Footer: Cancel and explicit action (Revoke, Retire, Delete, Destroy) side-by-side at the right, preserving focus and keyboard access.
- Overlong contents scroll *inside* the dialog, and long identifiers wrap without causing horizontal scrolling.

`operation_kind` provides the semantic action glyph (`delete`, `destroy`, `revoke`, `retire`); the actual action label remains explicit and resource-specific. Both the reversible nature of a Retire and the non-restoration of revoked Access Grants must be explained in the call site's content. Do not describe Retire as a permanent delete.

### Example invocation (Tenant Group)

```jinja
{{ destructive_modal.render('tenant-group-retire-modal',
    'Retire Tenant Group',
    'Selected Tenant Group',
    '',
    'tenant-group-retire-submit',
    action_label='Retire Group',
    notice='Stop future Membership selection while preserving existing history.',
    scope_value='Tenant Group binding',
    target_label='Group',
    scope_label='Tenant / Group',
    operation_kind='retire',
    impact_items=[...],
    warning='Retirement is blocked until Membership and Access Grant cleanup is complete.',
    presentation='governed') }}
```

The list in this example is abbreviated; use real `(icon, title, consequence)` tuples in implementation.

## Safety and compatibility

- The trigger carries `data-destructive-modal-id`, `data-destructive-submit-button-id`, `data-destructive-target`, and `data-destructive-scope` as relevant.
- The controller sets target and scope with `textContent`; no interpolation of user values into HTML.
- Confirm invokes **the existing hidden submit button** only after the explicit user action. Authorization, CSRF, provider authority and reconciliation are not replaced by UI confirmation.
- Preserve modal Escape/backdrop/Cancel, focus restoration and trap, and `aria-modal`/`aria-labelledby`.
- Keep existing `presentation='kubernetes'` and `presentation='steps'` for validated Kubernetes or multi-step operations. Do not silently migrate those workflows.
- `access_chrome` and `presentation='membership'` remain backward-compatible, but new governed actions should use `presentation='governed'`.
- No automatic mutation. A confirmation modal is not authorization and is not a remediation executor.

## Review checklist

At 390px and desktop widths, verify readable target/scope, vertical consequence list, contained scrolling, one warning, balanced footer, and light/dark semantic tokens. Run `djlint --check` on affected templates, focused Ruff/pytest contracts, and human visual UAT before official CI/CD admission.
