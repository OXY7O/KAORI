# KAORI Notification Center Final Lock v1.1

v1.1 supersedes Notification Center v1 with a professional KAORI inbox table and standardized hero context panel while preserving personal scope, canonical Active Work, Activity Audit separation, and Data Lifecycle ownership.

## Hero

The right hero panel is **Notification Posture** and uses the shared KAORI context pattern: semantic status, Unread metric, Active Work metric, one Activity Audit boundary statement, and the existing Activity Audit CTA when authorized.

## Notifications table

The Notifications workspace uses the shared KAORI table primitives and standard pagination. Columns are:

1. Notification
2. Event
3. Status
4. Received
5. State
6. Action

The Notification cell carries icon, title, message, optional detail, and unread indicator. Status and state use semantic labels. Actions remain right-aligned and explicit (`Open`, `Read`). Default Rows remains 5 with 5/10/25/50 options.

## Boundaries

- Notification Center remains personal/user-scoped.
- Activity Audit remains administrative/system-wide.
- Active Work mirrors canonical Jobs & Executions and does not create another registry.
- Persistent notifications remain governed by the Activity Audit lifecycle policy; transient toasts remain outside Data Lifecycle.
