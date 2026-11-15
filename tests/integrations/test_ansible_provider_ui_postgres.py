"""Real Flask routing, canonical integration CRUD and read-only UI state (#4817).

Runs with ephemeral PostgreSQL after schema initialization in issue branch QA.
Never hits an external Ansible provider or real infrastructure.
"""
from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app import create_app
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.user import User

INDEX = '/integrations/orchestration/ansible/'


def _authenticated_client(app, *, is_super_admin: bool = True):
    with app.app_context():
        identity = uuid4().hex[:12]
        user = User(
            username=f'ansible-ui-{identity}',
            email=f'{identity}@example.invalid',
            is_super_admin=is_super_admin,
            auth_source='database',
            account_is_active=True,
        )
        user.set_password('CI-only-synthetic-login-secret')
        db.session.add(user)
        db.session.commit()
        session_identity = user.get_id()
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = session_identity
        session['_fresh'] = True
        session['auth_source'] = 'database'
    return client


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match, 'Form CSRF protection is absent from rendered HTML'
    return match.group(1)


def test_real_provider_routes_registration_edit_and_safe_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    client = _authenticated_client(app)
    root = client.get(INDEX)
    assert root.status_code == 200
    assert b'Ansible Infrastructure Automation' in root.data
    assert b'Add Connection' in root.data
    assert b'Connection Registry' in root.data
    assert b'No Ansible connections found' in root.data

    selector = client.get('/integrations/providers/infrastructure_automation')
    assert selector.status_code == 200
    assert b'Ansible' in selector.data
    assert b'/integrations/orchestration/ansible/instances/new' in selector.data

    form_page = client.get(f'{INDEX}instances/new')
    assert form_page.status_code == 200
    token = _csrf(form_page.get_data(as_text=True))
    unique_name = f'Ansible CI {uuid4().hex[:8]}'
    saved = client.post(
        f'{INDEX}instances/new',
        data={
            'csrf_token': token,
            'name': unique_name,
            'description': 'Reviewed localhost source',
            'environment': 'testing',
            'enabled': 'on',
        },
    )
    assert saved.status_code in {302, 303}
    with app.app_context():
        instance = IntegrationInstance.query.filter_by(
            integration_type='infrastructure_automation', name=unique_name
        ).one()
        instance_id = instance.id
        assert instance.enabled is True
        assert instance.readiness_status == 'validation_required'
        assert instance.metadata_json['target_authority'] == 'worker-localhost-only'
        assert 'ssh_private_key' not in str(instance.metadata_json)

    detail_url = f'{INDEX}instances/{instance_id}'
    detail = client.get(detail_url)
    assert detail.status_code == 200
    assert unique_name.encode() in detail.data
    assert b'Run Local Read-only Test' in detail.data
    assert b'External Host Validation' in detail.data
    assert b'No execution history' in detail.data
    assert b'Not Verified' in detail.data

    fragment = client.get(INDEX, headers={'HX-Request': 'true', 'HX-Target': 'ansible-connections-registry'})
    assert fragment.status_code == 200
    assert b'ansible-connections-registry' in fragment.data
    assert b'Add Connection' not in fragment.data

    edit = client.get(f'{detail_url}/edit')
    assert edit.status_code == 200
    new_name = f'{unique_name} Updated'
    updated = client.post(
        f'{detail_url}/edit',
        data={
            'csrf_token': _csrf(edit.get_data(as_text=True)),
            'name': new_name,
            'description': 'Only identity changed',
            'environment': 'uat',
        },
    )
    assert updated.status_code in {302, 303}
    with app.app_context():
        instance = db.session.get(IntegrationInstance, instance_id)
        assert instance is not None
        assert instance.name == new_name
        assert instance.enabled is False
        assert instance.readiness_status == 'validation_required'

    # Disabled actions are rejected; bypassing the disabled HTML button is also denied.
    probe = client.post(
        f'{detail_url}/probe',
        data={'csrf_token': _csrf(client.get(detail_url).get_data(as_text=True))},
    )
    assert probe.status_code in {302, 303}
    with app.app_context():
        assert JobExecution.query.filter_by(
            integration_type='infrastructure_automation', integration_instance_id=instance_id
        ).count() == 0
    invalid = client.post(
        f'{INDEX}instances/new',
        data={
            'csrf_token': token,
            'name': 'unsafe',
            'environment': 'testing',
            'ssh_private_key': 'NEVER STORE',
        },
    )
    assert invalid.status_code == 400
    assert b'NEVER STORE' not in invalid.data


def test_authentication_and_csrf_deny_unapproved_management() -> None:
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    assert app.test_client().get(INDEX).status_code in {302, 401, 403}
    restricted = _authenticated_client(app, is_super_admin=False)
    assert restricted.get(INDEX).status_code == 403
    authorized = _authenticated_client(app)
    assert authorized.post(
        f'{INDEX}instances/new',
        data={'name': 'missing csrf', 'environment': 'testing'},
    ).status_code == 400
