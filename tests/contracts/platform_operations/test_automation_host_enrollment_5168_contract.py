"""#5168: host identity enrollment is scoped, CSRF-guarded and non-executable."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from app.infrastructure_automation.host_enrollment import enroll_host_for_connection
from app.infrastructure_automation.host_registry import AutomationHostIntent, AutomationInventoryDenied
from app.infrastructure_automation.workspace import project_host_assets

ROOT = Path(__file__).resolve().parents[3]


def _connection(**changes):
    values = {
        'id': 17,
        'enabled': False,
        'environment': 'laboratory',
        'integration_type': 'configuration_automation',
        'provider_key': 'ansible',
        'lifecycle_status': 'active',
        'name': 'Source-only Ansible',
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _assignment():
    host = SimpleNamespace(
        id='host-17',
        name='control-01',
        address='10.11.12.13',
        ssh_port=22,
        environment='laboratory',
        lifecycle_status='registered',
    )
    return SimpleNamespace(integration_instance_id=17, host=host, role='control_plane', enabled=True)


def test_source_only_connection_may_review_committed_host_without_execution():
    snapshot = project_host_assets(_connection(), [_assignment()])
    assert snapshot['state'] == 'requires_trust_admission'
    assert snapshot['pagination']['total_items'] == 1
    assert snapshot['rows'][0]['role'] == 'control_plane'
    assert snapshot['execution_authorized'] is False


@pytest.mark.parametrize(
    ('connection', 'role', 'name', 'address'),
    [
        (_connection(environment='production'), 'worker', 'worker-01', '10.1.2.3'),
        (_connection(provider_key='other'), 'worker', 'worker-01', '10.1.2.3'),
        (_connection(), 'etcd', 'worker-01', '10.1.2.3'),
        (_connection(), 'worker', 'node-01', '127.0.0.1'),
    ],
)
def test_invalid_host_scope_role_or_endpoint_denied_before_db_write(connection, role, name, address):
    with pytest.raises(AutomationInventoryDenied):
        enroll_host_for_connection(
            connection,
            AutomationHostIntent(name=name, environment='laboratory', address=address),
            role=role,
        )


def test_host_registration_is_a_separate_guarded_post_not_workspace_get():
    app = create_app('testing')
    endpoints = {rule.endpoint: rule for rule in app.url_map.iter_rules()}
    route = endpoints['platform_operations.infrastructure_automation_hosts.new']
    assert route.rule == '/platform-operations/infrastructure-automation/hosts/<int:connection_id>/new'
    assert 'GET' in route.methods and 'POST' in route.methods
    workspace = endpoints['platform_operations.infrastructure_automation.index']
    assert 'POST' not in workspace.methods
    template = (ROOT / 'app/templates/infrastructure_automation/host_enrollment.html').read_text()
    assert 'form.csrf_token' in template
    assert 'form.name' in template
    assert 'form.role' in template
    assert 'private_key' not in template
    assert 'password' not in template
    source = (ROOT / 'app/infrastructure_automation/host_routes.py').read_text()
    assert "@permission_required('integrations.manage')" in source
    assert "@permission_required('inventory.view')" in source
    for denied in ('ansible_runner.run', 'subprocess.run(', 'requests.post(', 'kubectl '):
        assert denied not in source
