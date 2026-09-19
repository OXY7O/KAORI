# Kubernetes TLS Certificate and Notification Delivery Audit — August 2026

This audit aligns ConfigMap Management, Secret Management, TLS Certificate Governance, operational toast delivery, Notification Deck visibility, and Activity Audit persistence with one KAORI contract.

## Decision boundary

KAORI now separates three concerns that were previously coupled through one Notification row:

- **Operational toast** — immediate feedback for the user who performed or is observing an operation.
- **Notification Deck** — persistent operational inbox for terminal results, destructive changes, security-sensitive decisions, and items that may require follow-up after navigation.
- **Activity Audit** — authoritative evidence for provider mutations and governance decisions, including successful events that should not create Deck noise.

The canonical delivery policies are:

| Policy | Activity Audit | Notification Deck |
|---|---|---|
| `audit_only` | Persist when the event is auditable | Hidden |
| `deck_on_failure` | Persist | Visible only for warning or error |
| `persistent` | Persist | Always visible |

`notifications.deck_visible` records the Deck decision explicitly. Hidden Activity Audit rows are marked read and excluded from user Notification Deck queries and unread counts. Administrative Activity Audit queries continue to include all rows.

## ConfigMap Management policy

| Event | Toast | Notification Deck | Activity Audit |
|---|---|---|---|
| Local validation or server dry-run | Transient/inline | No | No |
| Create/update success | Yes | No | Yes |
| Create/update warning or failure | Persistent | Yes | Yes |
| Delete success, warning, or failure | Persistent | Yes | Yes |

Create and update therefore use `deck_on_failure`, while delete uses `persistent`.

## Secret Management policy

| Event | Toast | Notification Deck | Activity Audit |
|---|---|---|---|
| Local validation or server dry-run | Transient/inline | No | No |
| Create/replace success | Yes | No | Yes |
| Create/replace warning or failure | Persistent | Yes | Yes |
| Delete success, warning, or failure | Persistent | Yes | Yes |
| Reveal request/approval/denial/security blocker | Yes | Yes | Yes |
| One-time reveal completed | Yes | No | Yes |

Secret values, decoded payloads, tokens, private keys, and certificate private-key material are never written to toast payloads, Notification metadata, Activity Audit metadata, database inventory records, or application logs.

## TLS Certificate Governance policy

TLS has two distinct execution models.

### TLS Inventory synchronization

TLS Inventory synchronization is a background `JobExecution`:

1. The accepted dispatch is shown through the canonical progress toast and job link.
2. No duplicate queued Notification Deck item is created.
3. Secret collection and Ingress mapping evidence are evaluated independently per cluster.
4. Terminal Activity Audit and Notification Deck evidence are persisted before the JobExecution is marked terminal.
5. The progress toast transitions to the terminal state without racing ahead of persistent evidence.

Terminal results:

- **Succeeded** — TLS Secret collection and Ingress mapping completed for all target clusters.
- **Partially succeeded** — one or more clusters failed, or TLS Secrets were collected but Ingress mapping evidence is incomplete because of RBAC/API limitations or another mapping-source failure.
- **Failed** — every target cluster failed or an unrecoverable worker failure occurred.
- **Canceled** — cooperative cancellation completed.

A cluster with successful Secret collection but incomplete Ingress mapping is not reported as fully current. The job, toast, Notification Deck, and Activity Audit state that host-coverage evidence requires review.

### TLS Secret rotation

TLS rotation is a foreground provider mutation with a server-side validation boundary:

1. Uploaded certificate and private-key files are size-limited and parsed safely.
2. Certificate/private-key pairing, validity, fingerprint, and SAN evidence are validated.
3. The live Secret is reread and checked for TLS type and resource-version drift.
4. Exactly one Kubernetes dry-run and one provider mutation are executed.
5. Provider success is separated from KAORI persistence success.
6. Rotation terminal results always use `persistent` delivery because certificate changes require governance evidence and may require follow-up.

A successful Kubernetes update followed by a KAORI persistence failure is a warning, not a false success or a provider rollback claim. The user is instructed to run TLS synchronization to reconcile inventory evidence.

## TLS collection evidence

The collector now preserves separate evidence for:

- TLS Secret collection;
- Ingress-to-TLS-Secret mapping.

Expected provider limitations are represented as evidence states. Unexpected server/client failures are not silently converted into empty results.

Additional corrections:

- TLS Secrets without namespace or name are excluded from reconciliation;
- duplicate Ingress consumers and duplicate host declarations are deduplicated;
- inventory collection parses only `tls.crt` and never reads or persists `tls.key`;
- `db.session.get()` replaces legacy model-query lookup paths within the audited TLS scope;
- active and terminal TLS workspaces use canonical `_page_workspace.html` and progress-toast components;
- legacy TLS toast and inventory-scope wrappers are removed.

## Migration and RBAC

Two migrations are introduced:

- `20260805_secret_ops_v2` migrates TLS rotation permission assignments from retired permission names to canonical Kubernetes Secret operation permissions.
- `20260805_notification_deck_v2` adds explicit Deck visibility and its user/query index.

The expected migration head is:

```text
20260805_notification_deck_v2
```

After database upgrade, the canonical RBAC catalog must be reseeded so migrated assignments and current permission definitions remain aligned.

## Removed compatibility paths

The audit removes:

- monolithic Secret routes and session-bound delete receipt behavior;
- TLS local toast builder;
- TLS `_inventory_scope.html`, `_content.html`, and `_sync_toast.html` wrappers;
- duplicate route-level mutation validation;
- legacy TLS permission aliases;
- active-sync compatibility route behavior.

Regression gates prevent these paths from being reintroduced.

## Validation boundary

The source audit covers static contracts, isolated mutation/receipt behavior, migration graph validation, Jinja and JavaScript syntax, source hygiene, canonical Inventory workspace preservation, and full contract comparison against the parent commit.

The audit environment does not provide Flask runtime dependencies, PostgreSQL, Kubernetes API access, a browser, Ruff, DjLint, or Pyright. Live migration, connected-cluster mutation, responsive/dark-mode browser behavior, and worker execution therefore require smoke testing in the KAORI development environment after application.
