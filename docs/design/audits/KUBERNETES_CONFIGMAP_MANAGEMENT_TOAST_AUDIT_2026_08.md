# Kubernetes ConfigMap Management and Operational Toast Audit — August 2026

## Scope

This audit covers ConfigMap Management landing, create, update, delete, live lookup, validation, impact evidence, Activity Audit, and the global operational toast used by authenticated and authentication layouts.

## Findings closed

- Landing counters now use current committed Configuration Inventory generations instead of historical rows.
- Namespace and ConfigMap targets remain live Kubernetes API evidence; Inventory is never a mutation target gate.
- ConfigMap parsing now validates DNS-subdomain object names label-by-label, namespace DNS labels, key rows, content kinds, canonical base64, combined merge size, update mode, duplicate keys, and the 1 MiB data boundary.
- Binary data remains base64 strings at the Kubernetes client boundary.
- Create and Update no longer use a generic validate/apply wrapper. Validation performs one dry-run. Final mutation performs one fresh dry-run and one mutation.
- Update remains protected by live `resourceVersion`; immutable ConfigMaps are blocked.
- Pod impact uses the current committed Pod generation, honors `inventory.pods` collection evidence, deduplicates workload identities, and uses canonical Pod posture.
- Delete validation does not send DELETE. It checks exact-name confirmation and `SelfSubjectAccessReview`, then issues a stateless signed receipt bound to the user, target, resource version, and ten-minute expiry.
- Final delete rereads the target, rejects drift, and uses a Kubernetes resource-version precondition.
- Persistent validation preview distinguishes Pending, Validated, and Failed and is invalidated by target, form, update-mode, exact-confirmation, or programmatic key-row changes.
- Operational feedback now uses one typed `OperationalFeedbackSpec` and one global toast component with semantic rail, compact status, Activity Audit context, dedupe, a four-item limit, pause/resume, and severity-based dismissal.
- User-initiated synchronization progress uses the canonical operational progress toast and shared progress-bar component instead of domain-specific cards or inline UI scripts.
- Legacy quick-action toast templates, layout handlers, ConfigMap operation notification wrapper, and Kubernetes operation compatibility component were deleted.

## Canonical ownership

| Boundary | Owner |
|---|---|
| Target and values | Live Kubernetes API |
| Known consumers | Current committed Pod Inventory |
| Validation and mutation orchestration | ConfigMap service modules |
| Destructive validation receipt | Signed stateless receipt service |
| Result feedback | Operational toast + Activity Audit |

## Legacy removals

- `app/templates/kubernetes/operations/_components.html`
- `app/templates/kubernetes/operations/configmaps/_operation_notification.html`
- `app/templates/components/navigation/_quick_sync_result.html`
- `app/templates/components/navigation/_operation_feedback_oob.html`
- `dismissQuickActionToast` layout handlers
- `quick_action_feedback` builder/session/bootstrap naming

## Validation boundary

Static, contract, pure validation, isolated mutation/receipt, Jinja, JavaScript, source-hygiene, code-health, and regression gates must pass. Live Kubernetes mutation and browser interaction remain deployment smoke tests because they require a registered cluster and a running KAORI application. The audit environment could not rebuild Tailwind assets because the configured package registry did not provide one locked dependency; the new toast reuses utilities already present in the retained stylesheet and introduces no new unique utility token.
