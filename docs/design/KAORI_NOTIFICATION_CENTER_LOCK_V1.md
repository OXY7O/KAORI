# KAORI Notification Center Final Lock v1

Status: Final Lock
Date: 2026-08-08
Owner: Notifications

## Purpose

The Notification Center is KAORI's personal operational inbox. It is intentionally separate from the administrative Activity Audit Log.

## Locked Information Architecture

- Page title: **Notification Center**.
- User-facing views: **Notifications** and **Active Work**.
- The internal `view=activity` compatibility key may remain, but visible tab copy must be **Active Work** so the personal page is not confused with Activity Audit.
- Notifications are login-scoped, `deck_visible=true`, non-authentication rows targeted to the current user.
- The full page uses standard 5/10/25/50 pagination and Title Case `Rows` typography.
- Active Work reads canonical `JobExecution` records and links to Jobs & Executions for full runtime evidence. It is not a second execution registry.
- Activity Audit remains system-wide and permission-gated.

## Lifecycle Boundary

Persistent Notification Center rows and Activity Audit rows share the `notifications` source table and the Data Lifecycle `operational_activity` policy. Audit-only rows are hidden from the personal inbox through `deck_visible=false` but remain retained. Transient toasts are not persisted and are outside lifecycle management.

## Presentation Contract

- Use KAORI semantic surfaces and quiet dark-mode presentation.
- Full-page workspace tabs use the framed workspace geometry; the compact top-bar deck uses a neutral segmented track.
- Whole-card Violet unread backgrounds are forbidden; unread state uses neutral elevation plus a compact semantic indicator.
- Standard shared progress presentation is used for determinate background work.
- Auto refresh remains every 15 seconds and must not replace the stable bell/drawer shell.
