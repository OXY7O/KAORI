# Ansible source-validation posture and capability truth

Authority: #4842, child corrective work to #4834/#4827 under #4796/#556.

## Correctness issue

Previously the Manage Connection Validation & Capabilities tab always displayed **Immutable Git Source: Checked** even after a CSRF-protected Git revalidation recorded `source_validation.status=blocked`. The hero duplicated that incorrect claim. This is not acceptable for operational review.

## Applied principle

The existing provider-owned presentation `source_validation_posture(connection)` renders three states derived exclusively from persisted `IntegrationInstance.metadata_json.source_validation`. As required by #4978, the committed-state predicate and immutable source/version pins are shared with domain-owned Kubespray preflight in `app/infrastructure_automation/kubernetes/source_policy.py`; the provider presentation cannot diverge from the Plan/worker qualification decision. GitHub retains Git transport and blob verification. The predicate compares the approved Git identity, revision, profile, required blob count and exact version policies:

- **Source Checked**: source evidence matches the currently recorded approved candidate. Does **not** imply worker/SSH/cluster readiness.
- **Source Blocked**: revalidation failed, the revision/version policy differs, or previously checked evidence no longer matches the current source.
- **Not Checked**: no qualifying committed Git verification exists.

Runtime/worker readiness remains Not Verified, and Kubernetes inventory remains Not Collected. All nine lifecycle operations (Discover, Preflight, Plan, Provision, Verify, Scale, Upgrade, Node Maintenance, Recovery) remain Blocked with an explicit required evidence reason. No privileged Run control or API is exposed.

Status is not derived from an unauthenticated browser value, a transient toast or a live provider call during ordinary GET. The Ansible Integration Kernel adapter uses the same committed source posture and cannot make `source_checked` synonymous with runtime Ready.

## Reviewer checks

```bash
python -m ruff check app/integrations/orchestration/configuration_automation/providers/ansible app/integrations/routes.py tests/contracts/integrations/test_ansible_source_posture_contract.py
python -m ruff format --check app/integrations/orchestration/configuration_automation/providers/ansible app/integrations/routes.py tests/contracts/integrations/test_ansible_source_posture_contract.py
djlint --check app/templates/integrations/orchestration/configuration_automation/providers/ansible/detail.html app/templates/integrations/orchestration/configuration_automation/providers/ansible/_detail_validation.html
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_source_posture_contract.py
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
```

No external host, Git credential, Kubernetes API, Ansible mutation, execution environment release, or production UAT is exercised by this change. This change does not supersede official Developer Check, Full Admission or human browser Visual QA.
