# Intelligence Workspace Standard

## Scope

This standard covers Recommendations, Rule Catalog, Alert Intelligence, and Automation Control.

## Hero

- Inventory-aligned composition.
- Maximum three metadata labels.
- Maximum two posture metrics.
- Stable posture title with one semantic badge.

## Records

- Responsive evidence records are the default.
- Native details are used for evidence expansion; no page-local JavaScript toggle implementation.
- Pagination uses `Showing a–b of n`, `Rows`, numeric pages, Previous, and Next.

## Capability states

- `Available`: implemented evidence or evaluator path.
- `Imported Signal`: evidence originates from an authoritative external source.
- `Reserved Plan`: disabled until provider, validation, and behavior contracts are complete.

MVP, placeholder, preview-only, and coming-soon labels are prohibited.

## Automation Control

Automation Control is presentation-complete but mutation-disabled by default. The configuration flag is `AUTOMATION_CONTROL_MUTATIONS_ENABLED`, defaulting to false. Direct POST requests are rejected with a Reserved Plan notification while disabled.
