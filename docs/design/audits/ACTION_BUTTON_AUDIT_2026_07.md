# Global Action Button Audit — July 2026

## Audit scope

The audit reviewed all Jinja HTML templates under `app/templates/` and classified 252 `<button>` controls plus action-styled links. Navigation controls, tabs, disclosure controls, pagination, icon-only utilities, and action buttons were separated before applying the mutation-button contract.

## Findings corrected

- `Save Readiness` in Protected Secret Reveal now uses Title Case, a Save icon, solid KAORI Violet, darker Violet hover and active states, visible focus treatment, and pointer/disabled cursors.
- Legacy blue primary styling in Alertmanager Configuration was replaced by KAORI Violet.
- Primary, destructive, and submit controls across Alertmanager, Prometheus, Kubernetes Operations, Reports, Settings, Users, Integrations, Governance, Inventory, Notifications, and shared components now explicitly expose the enabled pointer cursor and disabled cursor behavior.
- Static mutation labels found in sentence case were normalized to Title Case, including `Save Binding`, `Archive Selected`, `Run Now`, `Save Changes`, `Delete Schedule`, `Archive & Cleanup`, `Verify Protected Session`, `Validate Replacement`, `Replace Selected Data`, `Submit Reveal Request`, and `Reload Snapshot`.
- The Delete User confirmation now uses the standard destructive geometry and a Trash icon.
- Compact notification actions received explicit action icons and Title Case labels while retaining compact utility density.

## Intentional exceptions

The following remain outside the full action-button geometry:

- Sidebar and top-navigation controls.
- Tabs and segmented controls.
- Pagination.
- Expand/collapse controls.
- Icon-only table utilities with accessible labels.
- Overflow-menu items.

These controls are interaction components, but they are not page-level state mutation actions.

## Ongoing enforcement

`tests/ui/test_global_action_button_contract.py` protects the highest-risk global requirements:

- Protected Secret Reveal button wording and Violet contract.
- No legacy blue primary action in button markup.
- Primary and destructive action buttons include pointer and disabled cursor states.
- Known mutation labels remain in Title Case.
- Button documentation remains linked from the design documentation index.

Future migration should consolidate repeated class strings into a shared Jinja action-button macro after existing page workflows are stable. The macro must preserve the contract in `components/BUTTON.md` rather than introducing a second visual standard.
