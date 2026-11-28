# Alert Intelligence recommendation routing mode

Authority: #5450, #5228, #1512. Scope: recommendation-origin Kubernetes,
Object Storage and Artifact Registry. This is not a global kill switch for
every Notification Channels event or for separately qualified provider-origin
Vault delivery.

## Operation

Open **Intelligence → Alert Intelligence → Routing & Channels → Routing Mode**.
Read the current committed mode and select a mode, then Save Routing Mode.
Changing the configuration requires both `intelligence.view` and
`integrations.manage`. The form uses the current revision and CSRF; concurrent
stale submissions are rejected. Audit Activity records previous/new mode and
revision. The control is deployment-wide, independent of the workspace's
selected domain or asset.

| Mode | No policy | Matching enabled policy |
| --- | --- | --- |
| Channel Defaults | Eligible channel fallback for Kubernetes/Object Storage only | Governed policy |
| Policy Required | No delivery | Governed policy |
| Delivery Disabled | No delivery | No delivery |

Registry never uses fallback. Channel validation, manual test/preview,
non-alert notifications and Vault exact-instance delivery retain their own
controls. Existing worker scheduling/enablement remains necessary; mode
selection does not enable a worker or create a notification policy.

Recommend Policy Required for production after the receiving team has
approved policies, destinations, severities and cadence. Migration preserves
Channel Defaults; no deployment mode is changed by source merge alone.

## Rollout and rollback

1. Follow existing DBA migration contract. Pause affected dispatch and
   recovery workers for the schema/application transition; preserve backups,
   current revision and configuration. Apply the approved migration using the
   authorized migration executor, not the runtime principal. New revision:
   `20261128_alert_delivery_mode`. Verify singleton id=1, revision=1,
   mode=channel_defaults on a new upgrade and appropriate runtime DML access.
2. Deploy matching web and worker code after schema qualification. Recheck
   worker scheduling configuration independently. Do not start old workers
   alongside the new mode and claim the mode is enforced by both.
3. UAT using an approved disposable destination. Do not send production tests
   as part of qualification. Verify the matrix below and collect sanitized
   audit and delivery evidence. Explicitly select the intended mode after UAT.
4. Prefer restoring the intended previous mode with a new audited revision
   over downgrade. If schema/application downgrade is necessary, stop affected
   dispatch/recovery workers, back up committed mode/audit evidence, coordinate
   code/schema rollback with DBA, and require renewed acceptance before
   enabling delivery. The older code can restore implicit fallback and does
   not enforce this mode. Downgrade drops the singleton, not delivery history.

## UAT evidence

- Channel Defaults: no policy, eligible channel, policy mismatch, disabled
  policy, Registry no-policy denial, and unrelated notification event.
- Policy Required: no policy/no transport; matching policy/eligible channel;
  severity/label/channel mismatch; stale default retry and legacy dispatch
  denied; resolved requires successful firing and current policy permission.
- Delivery Disabled: firing/repeat/resolved and due generic retries blocked;
  case collection, owner/ACK/silence/verification remain operable.
- Re-enable: newly admitted work follows current policy; skipped recovery
  rows remain evidence and are not automatically replayed.
- Permission-negative and CSRF checks; two concurrent settings submissions
  reject the stale revision; inspect previous/new mode audit metadata.
- Confirm actual web, worker and PostgreSQL migration/recovery evidence;
  fixtures and CI alone do not qualify real provider delivery.

A mode save does not cancel network transport already admitted/in flight.
A blocked queued/failed replay is retained with a skipped reason, not deleted
or silently retried. A destination may still report messages accepted before
the mode change. Stop workers and verify provider outcomes if a strict
maintenance isolation boundary is required.
