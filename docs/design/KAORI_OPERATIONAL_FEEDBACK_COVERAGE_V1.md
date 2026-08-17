# KAORI Operational Feedback Coverage v1

Status: **Locked**
Date: **2026-08-08**

KAORI records operator-facing mutations through one canonical operational feedback boundary. The same normalized event payload drives immediate feedback and durable evidence; raw secret material is never included.

## Delivery Matrix

| Category | Operation Class | Toast / Immediate Feedback | Notification Center | Activity Audit |
| --- | --- | --- | --- | --- |
| ConfigMap Management | Create / Update success | Yes | No — routine success | Yes |
| ConfigMap Management | Delete success | Yes | Yes — destructive | Yes |
| ConfigMap Management | Warning / failure | Persistent | Yes | Yes |
| TLS Certificate | Rotation / bulk rotation terminal result | Yes | Yes | Yes |
| TLS Certificate | Background inventory sync | Activity Center while active; terminal feedback when complete | Terminal / attention evidence | Yes |
| Secret Management | Create / Replace success | Yes | No — secret value remains transient and routine success is audit-owned | Yes |
| Secret Management | Delete / approval / warning / failure | Persistent | Yes | Yes |
| Secret Management | One-time reveal completion | Yes | No — reveal value must not become inbox content | Yes |
| Integrations | Connection / binding Create, Update, Delete | Yes | Yes | Yes |
| Integrations | Validation / runtime background work | Activity Center while active; terminal feedback | Terminal / attention evidence | Yes |
| Reports | Generate / template / schedule / storage / archive actions | Yes | By delivery policy | Yes |
| Platform Operations | Retention policy / Secret Reveal policy and readiness changes | Yes | Yes | Yes |
| Platform Operations | Background lifecycle execution | Activity Center | Yes when persisted by policy | Yes |
| Access | User, Identity Provider, Role and access mutations | Yes | Yes — security significant | Yes |
| Settings | Account security changes | Yes | Yes — security significant | Yes |
| Settings | Personal display / locale preferences | Yes | No — routine personal preference | Yes |

## Category Ownership

Notification Center uses these canonical categories:

- **ConfigMap Management**
- **TLS Certificate**
- **Secret Management**
- **Integrations**
- **Reports**
- **Platform Operations**
- **Access**
- **Settings**

The stored event key remains unchanged. Category assignment is presentation metadata and a Notification Center filter boundary.

## Guardrails

- Validation-only operations may use transient feedback and do not have to create a Notification Center row.
- Background progress belongs to Activity Center / Jobs & Executions, not repeated progress toasts.
- Warning and failure outcomes that need operator attention are persistent unless a stricter security boundary explicitly requires audit-only behavior.
- Secret values, kubeconfigs, credentials, tokens, passwords, and private keys must never be copied into Notification Center or Activity Audit metadata.
- Activity Audit is the durable administrative evidence view. Notification Center is the personal, deck-visible subset of persisted operational outcomes.

## Notification Surface Style Contract

- Notification execution progress uses the shared `components/progress_bar.html` notification progress macros with a canonical `h-1.5` track.
- Activity Center job progress and operational progress toasts must render through the same notification progress macros; page-local progress heights are not permitted.
- HTMX page loading is a separate interaction signal and keeps the shared thin `components/loading_bar.html` `h-1` contract.
- CRUD and explicit operator actions that change persisted state must produce canonical toast feedback for success and actionable failure. Inline field validation remains beside the affected fields and may coexist with a concise failure toast.
