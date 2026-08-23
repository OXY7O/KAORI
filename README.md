KAORI Automation Control follow-up patch

This patch applies a focused polish pass on top of the Automation Control table/modal redesign:

- Rule Catalog row summaries now use concise global summaries instead of awkward hard truncation.
- Added visual spacing between registry/table blocks across Runbooks, Decisions, Execution, and Readiness tabs.
- Reworked the Binding Configuration, Execution Configuration, and Record Readiness Evidence modals into boxed, sectioned layouts with clearer hierarchy.
- Preserved existing routes, forms, field names, CSRF handling, and governance behavior.

Apply from the project root:

  unzip -o KAORI_automation_control_followup_polish_20260823.zip -d .
