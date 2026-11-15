# Ansible Integration workspace — registration, evidence and UAT

Authority: #4817 child of #4799, #4796 and approved #556. Work branch `kaori/issue-4817-ansible-provider-workspace`; Draft issue-scoped review, no authorization for production mutation.

## Navigation and architecture

`Integrations → Orchestration → Infrastructure Automation → Ansible` is the **existing** provider-neutral Integration Kernel with a new Orchestration capability in the canonical YAML taxonomy/provider matrix. The registration CTA points to the Ansible provider-owned registration form; canonical `IntegrationInstance` stores name/environment/enabled state, a pinned source SHA, and non-secret trust-gate metadata. No second provider instance table or schema migration.

**Read-only pilot only.** The provider UI distinguishes an enabled registry identity from validated external host readiness. `readiness_status=validation_required` even after a passing localhost task. It never displays a remote-host Ready badge, accepts SSH/private inventory/credential fields, or invokes Kubespray. Normal overview, detail and execution history views read committed KAORI records, not live Ansible requests. Full UI includes overview, 5-default filtered registry, add/edit, detail, scoped JobExecution timeline, latest allowlisted OS/kernel facts, capability boundary and stop/disable via editing lifecycle.

Source SHA is `OXY7O/kaori-operations@a182ddd04b353497021b3a089d3289128e999f78`. The explicit opt-in `APP_ENV=development|testing`, `KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true`, and `KAORI_ANSIBLE_OPERATIONS_SOURCE_PATH` fixed by operator on both web/worker are **not editable on the form**. Worker must have the exact checkout and correct queue registration. Positive UI POST uses canonical job dispatcher with `integration_type=infrastructure_automation`, `integration_instance_id` and scope `localhost:automation-worker`, so evidence can be correlated without scanning unrelated jobs.

## Review checklist

1. Navigate `/integrations/orchestration`; Infrastructure Automation capability and Ansible provider are visible and Add Connection resolves to `/integrations/orchestration/ansible/instances/new`.
2. On `/integrations/orchestration/ansible/`, inspect Hero/KPIs, guidance, search/status filter, 5-row pagination, empty and populated states in Violet light/dark and mobile. All actions use existing shared macros and semantic indicator labels, without red/green filled status blocks.
3. Register a Development/Testing/UAT name; confirm response and canonical record. Edit and disable; ensure no credential/inventory/source-path form fields. Malicious parameters and CSRF denial must not save secrets or enqueue a job.
4. In development/testing Dev Container only, set `KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED=true`, mount the exact Git source to the configured `KAORI_ANSIBLE_OPERATIONS_SOURCE_PATH`, install pinned `requirements/automation-worker.txt`, start dedicated `automation` Celery worker and normal PostgreSQL/Redis.
5. In Ansible detail, click **Run Local Read-only Test**. Verify the new scoped `JobExecution` appears and finally succeeds with pinned SHA, target worker-localhost, `changed=false`, non-empty OS/kernel facts and `environment_attestation=NOT VERIFIED`. For disabled/flag-off/invalid source/worker-off ensure no false Ready or unauthorized job.
6. Verify Jobs & Executions is the canonical full timeline authority; provider detail is a sanitized context projection. Record actual CI, Dev Container evidence, Visual QA screenshots (mobile/desktop, both themes), Human Acceptance and approved source/EE digest on the issue.

## Required gates

- `python -m ruff check app/integrations/orchestration/infrastructure_automation app/infrastructure_automation/source.py app/infrastructure_automation/tasks.py tests/contracts/integrations/test_ansible_provider_contract.py tests/integrations/test_ansible_provider_ui_postgres.py`
- `python -m ruff format --check app/integrations/orchestration/infrastructure_automation tests/contracts/integrations/test_ansible_provider_contract.py tests/integrations/test_ansible_provider_ui_postgres.py`
- `python -m pyright app/integrations/orchestration/infrastructure_automation`
- `djlint --check app/templates/integrations/orchestration/infrastructure_automation/providers/ansible`
- `python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_provider_contract.py tests/integrations/test_ansible_provider_ui_postgres.py`
- `python scripts/verify_ui_reuse.py` and `python scripts/verify_ui_style.py` (if relevant in the existing KAORI toolchain).

Pre-admission CI and ephemeral CI browser are **not** real Dev Container/production host UAT, official Developer Check/Full Admission, staging merge, or Human Acceptance. The real-host and Kubespray workstreams #4800–#4802 remain separate and blocked until approved prerequisites.
