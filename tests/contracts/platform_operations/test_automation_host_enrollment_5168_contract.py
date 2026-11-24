"""#5168: host identity enrollment is scoped, CSRF-guarded and non-executable."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from app.infrastructure_automation.host_enrollment import (
    enroll_host_for_connection,
    host_revision,
    retire_host_for_connection,
    update_host_for_connection,
)
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


def test_revision_changes_when_host_name_role_or_endpoint_changes():
    assignment = _assignment()
    assignment.id = 23
    assignment.updated_at = None
    assignment.host.updated_at = None
    original = host_revision(assignment)
    assignment.host.name = 'control-02'
    renamed = host_revision(assignment)
    assignment.role = 'worker'
    reassigned = host_revision(assignment)
    assignment.host.address = '10.11.12.14'
    assert len(original) == 64
    assert len({original, renamed, reassigned, host_revision(assignment)}) == 4


def test_edit_and_retirement_fail_closed_before_any_db_write_on_cross_connection():
    assignment = _assignment()
    assignment.updated_at = None
    assignment.host.updated_at = None
    for mutation in ('edit', 'retire'):
        with pytest.raises(AutomationInventoryDenied):
            if mutation == 'edit':
                update_host_for_connection(
                    _connection(id=18),
                    assignment,
                    AutomationHostIntent(name='control-01', environment='laboratory', address='10.11.12.13'),
                    role='worker',
                    expected_revision=host_revision(assignment),
                )
            else:
                retire_host_for_connection(
                    _connection(id=18),
                    assignment,
                    expected_revision=host_revision(assignment),
                    confirmation='control-01',
                )


def test_edit_and_retire_http_routes_are_permission_guarded_and_retire_is_post_only():
    app = create_app('testing')
    endpoints = {rule.endpoint: rule for rule in app.url_map.iter_rules()}
    edit = endpoints['platform_operations.infrastructure_automation_hosts.edit']
    retire = endpoints['platform_operations.infrastructure_automation_hosts.retire']
    assert 'GET' in edit.methods and 'POST' in edit.methods
    assert 'GET' not in retire.methods and 'POST' in retire.methods
    source = (ROOT / 'app/infrastructure_automation/host_routes.py').read_text()
    assert source.count("@permission_required('integrations.manage')") == 3
    assert source.count("@permission_required('inventory.view')") == 3
    edit_template = (ROOT / 'app/templates/infrastructure_automation/host_edit.html').read_text()
    assert 'form.csrf_token' in edit_template
    assert 'retirement_form.csrf_token' in edit_template
    assert 'retirement_form.confirm_name' in edit_template
    assert 'form.expected_revision' in edit_template
    assert 'password' not in edit_template and 'private_key' not in edit_template
