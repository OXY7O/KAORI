from __future__ import annotations

import os

import pytest

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

from app import create_app  # noqa: E402
from app.alertmanager.forms import AlertmanagerBindingForm, AlertmanagerInstanceForm  # noqa: E402
from app.alertmanager.service import add_alertmanager_binding, save_alertmanager_instance  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Cluster, User  # noqa: E402
from app.models.alertmanager import AlertmanagerInstance  # noqa: E402
from app.models.notification import Notification  # noqa: E402


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
    assert b'scope bindings' in inventory.data
    assert b'Integration posture' in inventory.data
    assert b'Alertmanager Integration Overview' in inventory.data
    assert b'Register Instance' in inventory.data

    partial = client.get(
        '/integrations/alertmanager?q=Cluster+A&per_page=5',
        headers={'HX-Request': 'true'},
    )
    assert partial.status_code == 200
    assert b'Cluster A Alertmanager' in partial.data
    assert b'alertmanager-inventory-content' not in partial.data
    assert b'alertmanager-inventory-filter-form' not in partial.data
    assert b'Rows per page' in partial.data

    detail = client.get(f'/integrations/alertmanager/instances/{instance.id}')
    assert detail.status_code == 200
    assert b'Instance Configuration' in detail.data
    assert b'Scope Bindings' in detail.data
    assert b'Full Validation' in detail.data
    assert b'Integration workflow' in detail.data
    assert b'Runtime Health & Diagnostics' in detail.data

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
    assert b'Initial Scope Binding' in response.data
    assert b'Alertmanager Scope &amp; Workflow' in response.data
    assert b'Test Connection' in response.data
    assert b'Connection Identity &amp; Contract' in response.data
    assert b'Connection Type Guide' in response.data


def test_draft_connection_test_uses_submitted_settings_without_creating_instance(app, monkeypatch) -> None:
    user = User(username='connection-admin', email='connection-admin@example.test', is_super_admin=True)
    db.session.add(user)
    db.session.commit()

    observed = {}

    def fake_test(form):
        observed['endpoint'] = form.endpoint
        observed['auth_type'] = form.auth_type
        observed['verify_ssl'] = form.verify_ssl
        return {
            'connected': True,
            'label': 'Connection verified',
            'response_time_ms': 18,
            'version': '0.33.1',
            'cluster_status': 'ready',
            'reason': 'The Alertmanager status API responded successfully.',
            'request_path': '/api/v2/status',
        }

    monkeypatch.setattr('app.alertmanager.routes.test_alertmanager_form_connection', fake_test)

    client = app.test_client()
    _login(client, user.id)
    response = client.post(
        '/integrations/alertmanager/instances/test-connection',
        data={
            'name': 'Draft Alertmanager',
            'deployment_type': 'shared',
            'endpoint': 'https://alertmanager.example.test:9093/',
            'auth_type': 'none',
            'timeout': '7',
            'verify_ssl': '1',
            'enabled': '1',
        },
        headers={'HX-Request': 'true'},
    )

    assert response.status_code == 200
    assert b'Connection verified' in response.data
    assert b'Reachable' in response.data
    assert b'0.33.1' in response.data
    assert b'18 ms' in response.data
    assert b'Full Validation' in response.data
    assert b'data-quick-action-toast' in response.data
    assert b'Saved to notifications' in response.data
    assert observed == {
        'endpoint': 'https://alertmanager.example.test:9093',
        'auth_type': 'none',
        'verify_ssl': True,
    }
    assert db.session.query(AlertmanagerInstance).count() == 0
    notification = db.session.query(Notification).one()
    assert notification.event_type == 'alertmanager_connection_test'
    assert notification.status == 'success'
    assert notification.metadata_json['submitted_name'] == 'Draft Alertmanager'


def test_registration_rejects_unreachable_connection_before_database_save(app, monkeypatch) -> None:
    user = User(username='register-admin', email='register-admin@example.test', is_super_admin=True)
    db.session.add(user)
    db.session.commit()

    def fake_test(_form):
        return {
            'connected': False,
            'label': 'Connection failed',
            'error': 'Connection refused by the submitted endpoint.',
            'reason': 'The Alertmanager status API was not reachable.',
            'failure_code': 'connection_refused',
            'endpoint_host': 'alertmanager.example.test',
            'request_path': '/api/v2/status',
        }

    monkeypatch.setattr('app.alertmanager.routes.test_alertmanager_form_connection', fake_test)

    client = app.test_client()
    _login(client, user.id)
    response = client.post(
        '/integrations/alertmanager/instances/new',
        data={
            'name': 'Rejected Alertmanager',
            'deployment_type': 'shared',
            'endpoint': 'https://alertmanager.example.test:9093',
            'auth_type': 'none',
            'timeout': '5',
            'verify_ssl': '1',
            'enabled': '1',
        },
    )

    assert response.status_code == 200
    assert b'Connection verification must pass before registration' in response.data
    assert b'Connection failed' in response.data
    assert db.session.query(AlertmanagerInstance).count() == 0
    notification = db.session.query(Notification).one()
    assert notification.event_type == 'alertmanager_instance_create_rejected'
    assert notification.status == 'error'


def test_registration_rechecks_reachability_then_redirects_to_full_validation_page(app, monkeypatch) -> None:
    user = User(username='register-success', email='register-success@example.test', is_super_admin=True)
    db.session.add(user)
    db.session.commit()

    observed = {'calls': 0}

    def fake_test(form):
        observed['calls'] += 1
        observed['endpoint'] = form.endpoint
        return {
            'connected': True,
            'label': 'Connection verified',
            'response_time_ms': 12,
            'version': '0.33.1',
            'cluster_status': 'ready',
            'reason': 'The Alertmanager status API responded successfully.',
            'request_path': '/api/v2/status',
        }

    monkeypatch.setattr('app.alertmanager.routes.test_alertmanager_form_connection', fake_test)

    client = app.test_client()
    _login(client, user.id)
    response = client.post(
        '/integrations/alertmanager/instances/new',
        data={
            'name': 'Verified Alertmanager',
            'deployment_type': 'shared',
            'endpoint': 'https://alertmanager.example.test:9093/',
            'auth_type': 'none',
            'timeout': '5',
            'verify_ssl': '1',
            'enabled': '1',
        },
    )

    assert response.status_code == 302
    instance = db.session.query(AlertmanagerInstance).one()
    assert response.headers['Location'].endswith(
        f'/integrations/alertmanager/instances/{instance.id}'
    )
    assert observed == {
        'calls': 1,
        'endpoint': 'https://alertmanager.example.test:9093',
    }
    notification = db.session.query(Notification).one()
    assert notification.event_type == 'alertmanager_instance_created'
    assert notification.status == 'success'
    assert notification.metadata_json['connection_response_time_ms'] == 12

