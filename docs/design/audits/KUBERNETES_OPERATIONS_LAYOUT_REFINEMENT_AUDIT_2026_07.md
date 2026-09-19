# Kubernetes Operations Layout Refinement Audit — July 2026

## Scope

- ConfigMap Create, Update, and Delete
- Secret Create, Replace, Delete, Reveal, single TLS Rotation, and Bulk TLS Rotation
- Kubernetes Inventory Hero context panels
- Configuration key inventory and Pod/Workload Tolerations

## Corrections

- Restored one-to-four-word helper copy to Inventory and operations Hero context metrics.
- Added the shared 22rem wide live-mutation rail.
- Kept primary Info Flow visible while secondary guidance is expandable and closed by default.
- Moved Secret Create Form Action Bar into the primary column.
- Separated Form Action Bar title and helper copy.
- Made Secret type selection visually explicit.
- Stacked workflow-card related actions to prevent compressed labels.
- Reduced Key Inventory typography from 14 px to the shared 12 px supporting-text token.
- Added compact pair spacing for Tolerations.
- Rebuilt Bulk TLS Rotation as peer upload cards with a full-width arrow flow.
- Fixed Secret Create validation to call `execute_secret_operation(..., dry_run=...)`.

## Data and safety boundary

No database migration is required. Secret values remain transient and excluded from KAORI persistence, notifications, and audit payloads. Server-side validation still runs before create or mutation.
