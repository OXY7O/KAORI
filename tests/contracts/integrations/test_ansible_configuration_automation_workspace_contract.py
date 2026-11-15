"""Issue #4827: registered and read-only Ansible provider workspace."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app import create_app
from app.integrations.orchestration.configuration_automation import frontpage, integration_module
from app.integrations.provider_matrix import provider_kind
from app.integrations.taxonomy import get_capability_definition

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = 'integrations/orchestration/configuration_automation/providers/ansible/frontpage.html'
PARTIAL = 'integrations/orchestration/configuration_automation/providers/ansible/_execution_registry.html'


class _Query:
    def __init__(self, records):
        self.records = records

    def filter_by(self, **fields):
        return _Query([job for job in self.records if all(getattr(job, k) == v for k, v in fields.items())])

    def filter(self, expression):
        # This minimal test double verifies no accidental ORM access beyond filter_by for empty records.
        return _Query(self.records)

    def count(self):
        return len(self.records)

    def order_by(self, *args):
        return self

    def offset(self, n):
        return _Query(self.records[n:])

    def limit(self, n):
        return _Query(self.records[:n])

    def all(self):
        return list(self.records)


def _stub_job_query(monkeypatch):
    fake = SimpleNamespace(
        query=_Query([]),
        status=SimpleNamespace(in_=lambda values: values, __eq__=lambda other: other),
        created_at=SimpleNamespace(desc=lambda: None),
        id=SimpleNamespace(desc=lambda: None),
    )
    monkeypatch.setattr(frontpage, 'JobExecution', fake)


def test_canonical_taxonomy_matrix_and_navigation_are_provider_first() -> None:
    capability = get_capability_definition('orchestration', 'configuration_automation')
    kind = provider_kind('configuration_automation', 'ansible')
    assert capability.label == 'Configuration Automation'
    assert kind.lifecycle == 'planned'
    assert kind.adapter_key == 'ansible_runner'
    assert integration_module.workspace_endpoint == 'integrations.ansible'
    assert integration_module.operations == frozenset()
    assert integration_module.worker_queue == 'automation'


def test_empty_persisted_workspace_does_not_claim_ready_or_run(monkeypatch) -> None:
    _stub_job_query(monkeypatch)
    context = frontpage.build_ansible_frontpage(status='invalid', page=100, per_page=800)
    assert context['registered_targets'] == 0
    assert context['provider_readiness'] == 'Not Configured'
    assert context['total_executions'] == 0
    assert context['successful_executions'] == 0
    assert context['pagination']['per_page'] == 5
    assert context['pagination']['page'] == 1
    assert context['executions'] == []


def test_full_and_htmx_templates_render_with_existing_violet_components(monkeypatch) -> None:
    _stub_job_query(monkeypatch)
    # The shared navbar expects KAORI's RBAC shape even for an anonymous principal.
    # Keep this render contract anonymous so navigation never queries user jobs;
    # authenticated authorization is independently enforced on the GET route.
    principal = SimpleNamespace(
        is_authenticated=False,
        id=None,
        username='ui-test',
        role_name='Viewer',
        has_permission=lambda permission: False,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    app = create_app('testing')
    with app.test_request_context('/integrations/ansible'):
        context = frontpage.build_ansible_frontpage()
        full = render_template(TEMPLATE, **context)
        partial = render_template(PARTIAL, **context)
    assert 'data-kaori-ansible-workspace' in full
    assert 'Configuration Automation' in full
    assert 'data-kaori-ansible-execution-registry' in full
    assert 'No committed Ansible executions' in full
    assert 'ansible-execution-registry' in partial
    assert 'data-kaori-canonical-registry-filter' in partial
    assert 'data-kaori-canonical-registry-footer' in partial
    assert 'hx-select="#ansible-execution-registry"' in partial
    assert 'Not Configured' in full
    assert 'ansible-runner' not in full.lower() or 'Ansible Runner' in full
    assert 'No remote execution instance admitted' in full


def test_no_external_or_secret_runners_in_get_workspace() -> None:
    source = (ROOT / 'app/integrations/orchestration/configuration_automation/frontpage.py').read_text()
    assert 'JobExecution.query.filter_by(job_type=_PILOT_JOB_TYPE, operation=_PILOT_OPERATION)' in source
    for forbidden in ('ansible_runner.run', 'subprocess.run', 'requests.get(', '.apply_async(', 'ssh_private_key'):
        assert forbidden not in source
    template = (ROOT / 'app/templates/' / TEMPLATE).read_text()
    assert 'run-playbook' not in template
    assert 'method="POST"' not in template
