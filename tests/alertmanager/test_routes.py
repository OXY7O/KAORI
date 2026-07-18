from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.alertmanager.forms import AlertmanagerBindingForm, AlertmanagerInstanceForm  # noqa: E402
from app.alertmanager.service import add_alertmanager_binding, save_alertmanager_instance  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Cluster, User  # noqa: E402


@pytest.fixture
def app():
    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def test_instance_inventory_detail_and_legacy_cluster_redirect(app) -> None:
    user = User(
        username='alertmanager-admin',
        email='alertmanager-admin@example.test',
        is_super_admin=True,
    )
    cluster = Cluster(
        name='Cluster A',
        environment='production',
        kubeconfig='apiVersion: v1\nclusters: []',
    )
    db.session.add_all([user, cluster])
    db.session.flush()

    instance = save_alertmanager_instance(
        form=AlertmanagerInstanceForm(
            name='Cluster A Alertmanager',
            description='Cluster source.',
            deployment_type='cluster_managed',
            endpoint='http://alertmanager:9093',
            auth_type='none',
            username=None,
            password=None,
            bearer_token=None,
            timeout=5,
            verify_ssl=True,
            enabled=True,
        )
    )
    add_alertmanager_binding(
        instance=instance,
        form=AlertmanagerBindingForm(
            scope_type='kubernetes_cluster',
            scope_key=cluster.id,
            binding_role='primary',
            priority=100,
            enabled=True,
        ),
    )

    client = app.test_client()
    _login(client, user.id)

    inventory = client.get('/integrations/alertmanager')
    assert inventory.status_code == 200
    assert b'Alertmanager Instance Registry' in inventory.data
    assert b'Cluster A Alertmanager' in inventory.data
    assert b'asset bindings' in inventory.data

    detail = client.get(f'/integrations/alertmanager/instances/{instance.id}')
    assert detail.status_code == 200
    assert b'Instance Configuration' in detail.data
    assert b'Asset Bindings' in detail.data
    assert b'Run full validation' in detail.data

    legacy = client.get(f'/integrations/alertmanager/cluster/{cluster.id}')
    assert legacy.status_code == 302
    assert legacy.headers['Location'].endswith(f'/integrations/alertmanager/instances/{instance.id}')


def test_new_instance_page_prefills_cluster_binding_context(app) -> None:
    user = User(username='admin', email='admin@example.test', is_super_admin=True)
    cluster = Cluster(
        name='Platform Cluster',
        environment='production',
        kubeconfig='apiVersion: v1\nclusters: []',
    )
    db.session.add_all([user, cluster])
    db.session.commit()

    client = app.test_client()
    _login(client, user.id)
    response = client.get(f'/integrations/alertmanager/instances/new?cluster_id={cluster.id}')

    assert response.status_code == 200
    assert b'Register Alertmanager Instance' in response.data
    assert b'Platform Cluster Alertmanager' in response.data
    assert b'Initial Binding' in response.data
