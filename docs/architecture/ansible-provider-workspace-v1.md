# Ansible Configuration Automation provider workspace — UI candidate

Authority: #556 → #4796 → #4799 (pilot worker) → #4827 (read-only UI). The Ansible provider belongs under **Integrations → Orchestration → Configuration Automation → Ansible**, not under Container Orchestrator (Kubernetes API).

## Delivered read-only workspace
- Canonical taxonomy and provider matrix entries. Ansible remains **planned** for registration/remote host operations and no instance is seeded.
- Existing Integration Kernel registers one `configuration_automation` module with no executable provider operations; the UI is linked through the existing Orchestration provider-workspace navigation. No duplicate integration registry or external provider client.
- Route `/integrations/ansible` is protected by existing `integrations.manage` RBAC. It renders a shared Violet Hero, overview metrics, Git source provenance, authority boundary and the canonical JobExecution evidence registry.
- The registry only queries `JobExecution` rows with `job_type=infrastructure_automation` and `operation=automation_localhost_host_facts`, ordered by committed creation timestamp. Unrelated domain jobs cannot appear.
- Default page size 5 via shared KAORI pagination. HTMX filter, clear filters, loading indicator, page size, paging, static empty state, light/dark shared tokens and accessible labels follow existing shared components.
- Source revision is the original approved `OXY7O/kaori-operations@a182ddd04b353497021b3a089d3289128e999f78` from #4799. CI pilot results from GitHub-hosted ephemeral test infrastructure are not treated as real instance evidence or shown as provider-connected records.
- No HTTP action to dispatch an Ansible job, no dynamic playbook selection, no SSH credentials, remote inventory or Kubernetes mutation from this page.

## Review commands

```bash
python -m ruff check app/integrations/orchestration/configuration_automation app/integrations/kernel/registry.py app/integrations/routes.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
python -m ruff format --check app/integrations/orchestration/configuration_automation app/integrations/kernel/registry.py app/integrations/routes.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
djlint --check app/templates/integrations/orchestration/configuration_automation/providers/ansible/frontpage.html app/templates/integrations/orchestration/configuration_automation/providers/ansible/_execution_registry.html
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
```

## Remaining gates
Operator registration, inventory/secret authority, source and EE signing, real-host discovery, mutations, Kubernetes provisioning, production enablement, admission and human visual UAT remain separate issues. A successful CI render does not prove this page is deployed in the user's KAORI instance. Before showing a live screen, merge through approved staging flow and complete real UI/Visual QA.
