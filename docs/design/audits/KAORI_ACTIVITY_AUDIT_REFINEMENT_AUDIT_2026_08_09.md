# KAORI Activity Audit Refinement Audit — 2026-08-09

## Status

**PASS — UI refinement baseline, not Access Final Lock.**

## Scope

Activity Audit was rebuilt as the system-wide administrative evidence workspace while preserving `app/notifications` as the canonical persistence/query owner and Access as navigation/control-plane ownership.

## Decisions

- Remove Read/Unread semantics from Activity Audit; delivery state remains owned by Notification Center.
- Replace lifetime summary posture with bounded 24-hour Events, Successful, Attention, and Actor evidence.
- Replace raw Event Type as the primary filter with canonical Category.
- Add a retained Time Range filter with a seven-day register default.
- Use shared KAORI loading, table, labels, pagination, and content-driven resource detail modal.
- Keep Activity Audit system-wide and permission-gated by the existing stable permission key.
- Keep Activity Audit and persistent Notification Center records under the same Data Lifecycle archive-first source.
- Defensively suppress sensitive metadata keys even if a producer violates the operational feedback contract.

## Register Contract

Desktop filter order is: Search Activity, Category, Status, Actor, Time Range. Rows default to 5 with 5/10/25/50 choices. Pagination renders Previous, numeric pages, and Next while preserving filter state through HTMX navigation.

## Evidence Detail

The Activity Details modal shows Activity Identity, Actor Context, Target Context, recorded Change Evidence when present, and curated Operational Metadata. It does not reconstruct values that were not persisted and never renders protected credential material.

## Remaining Access Work

Activity Audit is not independently final locked yet. Directory Provisioning and the remaining Access security decisions still need review before the Access domain Final Lock.
