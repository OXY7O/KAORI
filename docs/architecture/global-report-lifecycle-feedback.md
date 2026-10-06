# Global Report Lifecycle Feedback

## Scope

This foundation migration standardizes user feedback for the remaining report lifecycle routes:

- generated report archive, bulk archive, and restore;
- report template create, update, delete, and duplicate;
- report schedule create, update, toggle, delete, and manual execution.

It does not change report permissions, storage behavior, schedule execution, template validation, redirect destinations, or service return contracts.

## Feedback contract

Validation failures use `queue_transient_feedback()` and do not create Activity Audit records. Mutation outcomes use `record_operational_activity(..., queue_feedback=True)` so success and failure are visible as KAORI toast feedback and retained as operational evidence.

Metadata is restricted to identifiers, requested counts, generated report identifiers, and an explicit outcome. Form values, report content, storage paths, credentials, and raw request payloads must not be persisted in feedback metadata.

## Event types

- `generated_reports_bulk_archive`
- `generated_report_archive`
- `generated_report_restore`
- `report_template_create`
- `report_template_update`
- `report_template_delete`
- `report_template_duplicate`
- `report_schedule_create`
- `report_schedule_update`
- `report_schedule_toggle`
- `report_schedule_delete`
- `report_schedule_run`

## Validation and rollback

Run the notification contract tests, report functional tests, architecture boundary verifier, and the full quality gate. The patch can be rolled back by reverting the route and contract-test changes; no database migration is introduced.
