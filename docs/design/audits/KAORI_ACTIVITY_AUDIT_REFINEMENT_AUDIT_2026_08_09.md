# KAORI Activity Audit Refinement Audit — 2026-08-09

## Status

**PASS — UI refinement baseline, not Access Final Lock.**

## Scope

Activity Audit was rebuilt as the system-wide administrative evidence workspace while preserving `app/platform_operations/notifications` as the canonical persistence/query owner and Access as navigation/control-plane ownership.

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

The Activity Details modal uses the established KAORI evidence layout: Activity Summary, three balanced context cards (Actor & Access, Execution & Trace, Context & Target), Recorded Changes with before/after evidence when present, and curated Operational Metadata. The modal remains content-driven, does not reconstruct values that were not persisted, and never renders protected credential material.

## Remaining Access Work

Activity Audit is not independently final locked yet. Directory Provisioning and the remaining Access security decisions still need review before the Access domain Final Lock.

## Detail Evidence Refinement v1.26

The Activity Details modal no longer presents a flat Operational Metadata dump. The final inspection order is Activity Summary, conditional Failure Summary, compact Execution Evidence, Actor & Access plus Target Context, Recorded Changes when present, Trace References, optional Additional Evidence, and Technical Evidence collapsed by default. Execution counters and trace identifiers are separated from low-level diagnostics, duplicated category/target/timestamp values are not repeated across multiple cards, and raw failure strings are redacted and length-bounded before they can appear under Technical Evidence.


## Adaptive Detail Modal Refinement v1.27

The Activity Details modal is widened to `max-w-6xl` while remaining content-driven. Evidence hierarchy is capability-driven rather than event-name-driven: failure interpretation appears only for warning/error evidence, execution metrics only when recorded, before/after changes only when available, curated additional evidence only when non-duplicated metadata remains, and technical diagnostics stay collapsed by default. The header carries the operator-facing activity message, Actor & Access and Target Context use a balanced two-column composition, Trace References use a compact register instead of large evidence cards, and the same modal grammar is intended to cover success, failure, change, background, and security-sensitive events without event-specific template branches.
