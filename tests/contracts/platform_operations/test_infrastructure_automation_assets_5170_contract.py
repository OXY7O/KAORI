"""#5170: permission-scoped committed host assets under Infrastructure Automation."""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template

from app import create_app
from app.infrastructure_automation.workspace import project_host_assets

PARTIAL = 'infrastructure_automation/_lifecycle_workspace.html'


def _connection(**changes):
    values = {
        'id': 17,
        'enabled': True,
        'environment': 'laboratory',
        'integration_type': 'configuration_automation',
        'provider_key': 'ansible',
        'lifecycle_status': 'active',
        'name': 'Lab Ansible',
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _assignment(position: int, *, connection_id: int = 17, role: str = 'worker', environment: str = 'laboratory'):
    host = SimpleNamespace(
        id=f'host-{position:02d}',
        name=f'lab-{position:02d}',
        environment=environment,
        address=f'10.11.12.{position}',
        ssh_port=22,
        lifecycle_status='registered',
    )
    return SimpleNamespace(
        id=position,
        integration_instance_id=connection_id,
        role=role,
        enabled=True,
        host=host,
    )


def test_five_row_pages_share_one_all_member_fingerprint():
    assignments = [_assignment(i, role='control_plane' if i == 1 else 'worker') for i in range(1, 8)]
    first = project_host_assets(_connection(), assignments, page=1)
    second = project_host_assets(_connection(), assignments, page=2)
    assert first['state'] == second['state'] == 'requires_trust_admission'
    assert first['fingerprint'] == second['fingerprint']
    assert first['pagination']['per_page'] == 5
    assert len(first['rows']) == 5
    assert len(second['rows']) == 2
    assert second['pagination']['start_item'] == 6
    assert first['execution_authorized'] is False
    assert second['execution_authorized'] is False


def test_unqualified_cross_connection_disabled_and_oversized_memberships_show_no_host_endpoints():
    valid = [_assignment(1), _assignment(2)]
    cases = [
        (_connection(), [_assignment(1), _assignment(2, connection_id=18)]),
        (_connection(enabled=False), valid),
        (_connection(environment='production'), valid),
        (_connection(), [_assignment(1, environment='other')]),
        (_connection(), [_assignment(i) for i in range(1, 258)]),
    ]
    for connection, assignments in cases:
        view = project_host_assets(connection, assignments)
        assert view['state'] == 'blocked'
        assert view['rows'] == []
        assert view['fingerprint'] is None
        assert view['execution_authorized'] is False


def test_immutable_inventory_role_changes_fingerprint_and_clamps_page():
    first = project_host_assets(_connection(), [_assignment(1), _assignment(2)], page=100)
    second = project_host_assets(_connection(), [_assignment(1, role='control_plane'), _assignment(2)], page=100)
    assert first['pagination']['page'] == 1
    assert len(first['rows']) == 2
    assert first['fingerprint'] != second['fingerprint']


def test_permission_denial_template_never_discloses_endpoint():
    app = create_app('testing')
    details = SimpleNamespace(
        connection=_connection(),
        profile_key='kubespray',
        repository='',
        source_revision='',
        source_state='blocked',
        preflight=SimpleNamespace(
            state='blocked',
            review_verified_gates=0,
            review_required_gates=8,
            governance_verified_gates=0,
            governance_required_gates=2,
            next_review_requirement='Host trust',
        ),
        plan=SimpleNamespace(state='blocked', description='Plan blocked'),
        can_inventory=False,
        can_jobs=False,
        cluster_bindings=[],
        jobs=[],
        assets=None,
    )
    from app.common.pagination import build_pagination_window, pagination_payload

    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        rendered = render_template(
            PARTIAL,
            details=details,
            connections=[details.connection],
            pagination=pagination_payload(build_pagination_window(total_items=1)),
            total_connections=1,
            selected_query='',
            selected_connection_id=17,
            can_inventory=False,
            can_jobs=False,
        )
    assert 'Assets &amp; Inventories' in rendered
    assert 'Inventory view permission is required' in rendered
    assert '10.11.12.' not in rendered
    assert 'Run Kubespray' not in rendered
    assert '<form method="POST"' not in rendered
