# Ansible–Kubernetes canonical asset correlation — read-only

Authority: issue #4845, under #4834/#4796/#556. This extends the existing Integrations → Orchestration → Ansible Manage Connection → Inventory & Lifecycle tab.

The read model selects only committed `IntegrationBinding` rows belonging to the requested canonical `IntegrationInstance` where `asset_type=kubernetes_cluster`. For those already bound keys, it batch-reads the authoritative KAORI `Cluster` identity and presents cluster name, environment, enabled association, and persisted binding-validation status. It never invents a cluster from Git inventory or shows unrelated binding records from another provider connection.

A missing/stale Cluster record is explicitly labeled as an unresolved identity. `validation_status=ready` or `enabled=true` on a binding **does not** grant Ansible Run permission or prove Kubernetes API/SSH readiness. Each row remains `execution_authorized=False`. No source/credential/cluster external HTTP request, cluster mutation or binding write occurs.

The existing shared canonical pagination is reused with `inventory_page` / `inventory_per_page` (default 5) independent of Runtime History paging. The inventory table supports HTMX scoped pagination and retains correct connection identity.

Focused QA:

```bash
python -m ruff check app/integrations/orchestration/configuration_automation/providers/ansible/service.py app/integrations/routes.py tests/integrations/test_ansible_cluster_binding_read_model.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
python -m ruff format --check app/integrations/orchestration/configuration_automation/providers/ansible/service.py app/integrations/routes.py tests/integrations/test_ansible_cluster_binding_read_model.py tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
djlint --check app/templates/integrations/orchestration/configuration_automation/providers/ansible/_detail_inventory.html app/templates/integrations/orchestration/configuration_automation/providers/ansible/detail.html
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_configuration_automation_workspace_contract.py
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kaori_test python -m pytest -q -p no:cacheprovider tests/integrations/test_ansible_cluster_binding_read_model.py
```

The integration requires a disposable PostgreSQL service for the DB test, as the existing Ansible source-registration suite already does. Browser Visual QA / UAT remains a separate gate; no infrastructure target execution is authorized.
