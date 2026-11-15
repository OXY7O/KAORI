"""#4845: Ansible inventory reads canonical Kubernetes asset associations only.

A disposable PostgreSQL database is required. No Ansible SSH or Kubernetes API
connection is ever created by these tests.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions.db import db
from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    bound_kubernetes_targets,
)
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance

pytestmark = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL', '').startswith('postgresql://postgres:postgres@localhost:5432/kaori_test'),
    reason='Requires disposable localhost PostgreSQL KAORI test database',
)


@pytest.fixture
def app(monkeypatch):
    application = create_app('testing')
    application.config['WTF_CSRF_ENABLED'] = False
    principal = SimpleNamespace(
        id=1,
        is_authenticated=True,
        username='ansible-inventory-reviewer',
        role_name='super_admin',
        has_permission=lambda _: True,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def _connection(name):
    row = IntegrationInstance()
    row.integration_type = 'configuration_automation'
    row.provider_key = 'ansible'
    row.adapter_key = 'ansible_runner'
    row.name = name
    row.environment = 'laboratory'
    row.enabled = False
    row.lifecycle_status = 'active'
    row.readiness_status = 'validation_required'
    row.metadata_json = {'source_validation': {'status': 'blocked'}, 'execution_enabled': False}
    db.session.add(row)
    db.session.flush()
    return row


def _binding(connection, asset_key, *, asset_type='kubernetes_cluster', enabled=True):
    row = IntegrationBinding()
    row.integration_instance_id = connection.id
    row.asset_type = asset_type
    row.asset_key = asset_key
    row.binding_role = 'primary'
    row.priority = 100
    row.enabled = enabled
    row.validation_status = 'ready'
    db.session.add(row)
    return row


def test_bounded_cluster_readback_is_connection_scoped_and_never_authorizes_run(app):
    with app.app_context():
        first = _connection('Kubespray Lab A')
        second = _connection('Kubespray Lab B')
        cluster = Cluster(
            id='11111111-1111-4111-8111-111111111111',
            name='lab-kubernetes',
            environment='laboratory',
            status='connected',
        )
        db.session.add(cluster)
        db.session.flush()
        _binding(first, cluster.id)
        _binding(first, '22222222-2222-4222-8222-222222222222')
        _binding(first, 'unrelated', asset_type='linux_host')
        _binding(second, cluster.id)
        db.session.commit()

        rows, pagination = bound_kubernetes_targets(first)
        assert pagination['total_items'] == 2
        assert pagination['per_page'] == 5
        assert len(rows) == 2
        resolved = next(row for row in rows if row['identity_resolved'])
        missing = next(row for row in rows if not row['identity_resolved'])
        assert resolved['cluster_name'] == 'lab-kubernetes'
        assert resolved['environment'] == 'laboratory'
        assert resolved['validation_status'] == 'ready'
        assert resolved['execution_authorized'] is False
        assert missing['cluster_name'] == 'Cluster identity missing'
        assert missing['cluster_id'] is None
        assert missing['execution_authorized'] is False

        other, other_page = bound_kubernetes_targets(second)
        assert other_page['total_items'] == 1
        assert len(other) == 1
        assert all(row['execution_authorized'] is False for row in other)

        page = app.test_client().get(f'/integrations/ansible/connections/{first.id}#inventory')
        assert page.status_code == 200
        assert b'lab-kubernetes' in page.data
        assert b'Cluster identity missing' in page.data
        assert b'No infrastructure mutation controls are enabled' in page.data
        assert b'Blocked' in page.data

        partial = app.test_client().get(
            f'/integrations/ansible/connections/{first.id}',
            headers={'HX-Request': 'true', 'HX-Target': 'ansible-inventory-registry'},
        )
        assert partial.status_code == 200
        assert b'data-kaori-ansible-inventory-registry' in partial.data
        assert b'lab-kubernetes' in partial.data
        assert b'dashboard_content' not in partial.data


def test_cluster_binding_pagination_is_five_and_pages_do_not_overlap(app):
    with app.app_context():
        connection = _connection('Kubespray Paginated')
        for index in range(7):
            cluster = Cluster(
                id=f'10000000-0000-4000-8000-{index:012d}',
                name=f'lab-cluster-{index}',
                environment='laboratory',
            )
            db.session.add(cluster)
            _binding(connection, cluster.id)
        db.session.commit()
        first, p1 = bound_kubernetes_targets(connection, page=1)
        second, p2 = bound_kubernetes_targets(connection, page=2)
        assert len(first) == 5
        assert len(second) == 2
        assert p1['total_items'] == p2['total_items'] == 7
        assert p1['total_pages'] == p2['total_pages'] == 2
        assert {row['cluster_id'] for row in first}.isdisjoint({row['cluster_id'] for row in second})
        assert all(row['execution_authorized'] is False for row in first + second)
