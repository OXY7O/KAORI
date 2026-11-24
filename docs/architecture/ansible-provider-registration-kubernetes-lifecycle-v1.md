# Ansible provider registration · Kubernetes Lifecycle (Kubespray) v1

**Authority:** #556, #4796, #4799, implementation #4834 and UI follow-up #4858. Status: reviewed candidate in `kaori/review/staging-uat`; awaiting Dev Container UAT/Human Acceptance. Not official `kaori/staging`, production or cluster execution admission.

## Product navigation
`Integrations → Orchestration → Configuration Automation → Ansible → Choose Automation Profile → Kubernetes Lifecycle → Add Connection → Manage Connection`.

Ansible is the reusable configuration-automation **provider**. Kubernetes Lifecycle is the first managed automation **profile** using Kubespray, not a second Kubernetes API provider or a second Ansible worker. Future Linux, Middleware/Database and Network profiles remain visible as *planned* without active registration until their own issues and compatibility authority are approved.

## Canonical connection lifecycle
The existing `IntegrationInstance` table owns the single canonical provider identity `configuration_automation:ansible`; `metadata_json` holds reviewed **non-secret** source and version policy, source-check evidence, and explicitly disabled operation flags. No parallel integration database tables, injected playbook inventories, plaintext host keys or custom SQL migration.

- The domain-owned `app/infrastructure_automation/kubernetes/source_policy.py` defines the exact reviewed Git and toolchain candidate policy shared by source posture and Kubespray preflight (#4978). The GitHub adapter uses those pins without transferring provider transport into the domain.
- The public GitHub adapter verifies a **fixed candidate** `OXY7O/kaori-operations@63db48309cbb6d261c27cf54f60bfe885a21f770` by a trusted TLS request with bounded response size, timeouts, redirect rejection and ambient-proxy refusal.
- The verifier checks a Git commit identity, exact tree SHA and expected immutable Git blob hashes for the Kubespray v2.32.0 compatibility profile, source manifest, localhost facts playbook, example inventory, and pinned Ansible/Runner dependencies. The non-executable profile is from independently reviewed `kaori-operations#5` / PR #6, merged to upstream main at the exact pinned SHA. Its merge tree `59bd02d6e1fade7dc0573f275e36f08001a4ecfc` matches reviewed head `873fcfb3a91825b5eed71ac8710bb674084b7ae5`; four original profile/manifest/playbook/inventory blob identities remain unchanged, and the secured EE requirements blob is `1765812c981fc4bca9acd782a4f6584c7ce0e8bb`.
- Validate Source issues a time-limited, user-bound and full-form-fingerprint proof. Save requires that proof; rejected/missing source or stale/modified form cannot register. The form does **not** receive GitHub or SSH credentials.
- On registration `IntegrationInstance.enabled=False`, `readiness_status=validation_required`, and `mutation_authorized=False`. Successful source-check evidence does not mark the worker, GitHub App, Kubernetes API or target asset ready.
- Ansible Core 2.19.15 and Ansible Runner 2.4.3 are **candidate package version policy**, Kubespray v2.32.0 is a pinned release/profile, not installed runtime detection. User-provided EE digest is **reference only** until independent image build/signed provenance and runtime validation.
- Revalidate Source is a CSRF-protected POST to the same pinned Git authority, committed to canonical metadata with an Activity Audit. There is no GET side effect. Denial keeps remote operations blocked.

### Superseded immutable source

The former candidate `831ab7c114b1c1ba777c08ab79c91415ad8d465d` and Ansible Core 2.19.3 are no longer qualified. Existing connection records and old source/host/Plan evidence are retained for audit, not rewritten or silently promoted. Register a separately validated replacement connection using the new accepted source, then explicitly enroll/requalify its target inventory and access references under the existing governance boundaries. Revalidate Source never edits the pinned revision. An in-place source migration is not part of the approved immutable registration workflow. The separate localhost pilot pin remains unchanged under #5066. No signed EE, actual remote access, or execution admission follows from static source parity.

## UI reuse
The Ansible provider landing uses the approved shared provider frontpage Hero/metric cards and canonical `table_registry`/pagination components. The Add Connection page follows the existing MinIO-style **Form + Right Context** registration pattern: Connection Identity; a bordered Git Source & Validation section using the shared `connection_validation_header` with **Validate Source** as the source-owned pre-save POST action; Compatibility & Execution References; and the shared `_provider_registration_actions` footer with reactive **Source Validation Required / Source Validated** status, Cancel and gated **Save Connection**. The context rail uses the shared `_provider_registration_context` for ordered registration steps and the Orchestration operational workspace. The shared footer's default Test Connection language remains unchanged for Kubernetes, MinIO and other connection-based integrations; Ansible passes source-specific copy without a new component.

The initial Add form intentionally leaves **Connection Name**, **Git Repository** and **Git Commit SHA** empty. WTForms `render_kw` displays a suggested name and the exact approved Git source/revision as **placeholders**, never as submitted defaults. Operators explicitly enter the source; submitted values remain visible if validation is rejected. The immutable source allowlist is still checked by `require_registration_policy` and `verify_public_kubespray_source`; empty inputs fail closed. This is a UI admission refinement, not permission to register another repository or commit.

`connectionVerified` represents only the current signed **source proof**, not execution readiness. The input/change handlers clear the user-bound hidden proof and disable Save if any registration field changes. Source verification submits `action=test`; Save submits `action=save` only with valid proof. The server is authoritative for validation and CSRF/RBAC regardless of browser state. This first slice offers **Add** only and does not invent an Edit route.

The manage page reuses `framed_workspace_tabs`, shared posture, table and readiness components for:
1. Configuration
2. Validation & Capabilities
3. Runtime & History
4. Inventory & Lifecycle

**Configuration display** uses the same `_provider_configuration_contract.html` macro as MinIO, Vault, Harbor, Metrics Source and Alertmanager: four identity/version summary cards, four committed Git/EE evidence fields, provider-owned Operational Context and an authority footer. The Ansible variant supplies source-appropriate Guide, contract/evidence copy and monospaced hash presentation through existing shared macro parameters. Because this first reviewed profile is **immutable and does not register an Edit route**, `configure_url=none` renders a noninteractive **Immutable Source** metadata label instead of an invalid Configure Connection action. Existing editable providers retain their current Configure link and defaults. Committed source proof is not evidence that the EE, automation worker, inventory or Kubernetes execution is admitted. The display performs no live Git/provider request and does not alter the approved source or version values.

Runtime history is scoped by `JobExecution.integration_instance_id`; the previous unbound localhost pilot jobs are **not** misrepresented as Kubernetes connection jobs. Inventory lifecycle remains `not_collected` and the existing Kubernetes Cluster identity continues authoritative for actual API/node state. No live provider calls or fabricated 0 Ready results are used as evidence of an admitted cluster.

## Operational feedback and Notification Deck

Ansible source registration uses the canonical KAORI Operational Toast in the authenticated shell; the previous full-width, form-local Source Registration alert has been retired. **Validate Source** success/failure, invalid inputs, unsupported actions, rejected candidate Git policy, stale/changed/expired proof and failed registration each emit one sanitized `record_operational_activity(..., queue_feedback=True, delivery_policy='audit_only')` result. These user-triggered synchronous outcomes explicitly set the existing `feedback_delivery='toast'` metadata override, because the generic background-event classifier treats event names containing `validation` as Activity Center progress. They appear in a top-right toast and in Activity Audit, **not** as new Notification Deck items. Field-specific WTForms errors remain under the affected control; source-proof invalidation and the persistent **Source Validation Required** footer are independent state, not another toast.

Successful **Save Connection** retains its existing single `ansible_source_connection_registered` persisted Activity Audit event and redirect toast; the existing Integrations event delivery policy controls Notification Deck visibility. Connection detail **Revalidate Source** still commits validation evidence and uses its existing Action Audit/Deck feedback path; never emit two receipts for one action. Ansible `ansible_source_` notification events are categorized as **Integrations** through the approved event category registry. Validation errors expose bounded approved field labels and safe fixed messages only, never raw verifier/DB diagnostics or signed proof tokens.

Source-only verification remains distinct from Full Validation, inventory/worker admission, Ansible execution and Kubernetes mutation. No operation gains authority because a success toast appeared.

## Gate boundary
The source adapter is a deliberately narrow public *source read* seam. A future private GitHub App adapter/source-grant implementation must reuse the admitted Source Control authority rather than opening arbitrary Git URLs. No remote SSH, Kubernetes installation, node patching, upgrade, credential selection or arbitrary playbook execution is provided by these pages. More complete Ansible/Kubespray lifecycle operations remain under issues #4800/#4801/#4802 and separate child workstreams.

## Focused Developer Check
```bash
python -m ruff check app/integrations/orchestration/configuration_automation app/integrations/source_control/source_control/providers/github/public_automation_source.py app/integrations/routes.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py tests/integrations/test_ansible_public_git_source.py
python -m ruff format --check app/integrations/orchestration/configuration_automation app/integrations/source_control/source_control/providers/github/public_automation_source.py app/integrations/routes.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py tests/integrations/test_ansible_public_git_source.py
djlint --check app/templates/integrations/orchestration/configuration_automation/providers/ansible/*.html app/templates/integrations/partials/_domain_workspace.html
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py tests/integrations/test_ansible_public_git_source.py
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
```

The CI render/DB registration tests must be complemented with actual authenticated browser UAT on deployed KAORI, light/dark visual QA, explicit Human Acceptance and normal Full Admission before staging/main promotion.
