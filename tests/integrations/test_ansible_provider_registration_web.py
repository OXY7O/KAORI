"""Issue #4834 functional HTTP registration proof backed by temporary PostgreSQL.

Only run when a dedicated TEST_DATABASE_URL is supplied by the pre-admission
GitHub Actions service container; never connect to a developer/production DB.
"""

from __future__ import annotations

import os
import re
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions.db import db
from app.integrations import routes
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
    PublicSourceEvidence,
)
from app.models.integration import IntegrationInstance

pytestmark = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL', '').startswith('postgresql://'),
    reason='Requires a dedicated temporary PostgreSQL TEST_DATABASE_URL',
)


@pytest.fixture
def app(monkeypatch):
    application = create_app('testing')
    application.config['WTF_CSRF_ENABLED'] = False
    with application.app_context():
        db.create_all()
    principal = SimpleNamespace(
        id=1,
        is_authenticated=True,
        username='ansible-test-operator',
        role_name='super_admin',
        has_permission=lambda _: True,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **_: None)
    monkeypatch.setattr(
        routes,
        'verify_public_kubespray_source',
        lambda repo, sha: (
            PublicSourceEvidence(
                repository=REPOSITORY,
                revision=SOURCE_CANDIDATE_SHA,
                tree_sha='a' * 40,
                profile_key=PROFILE_KEY,
                checked_files=5,
                observed_at='2026-11-15T12:00:00+00:00',
            )
            if repo == REPOSITORY and sha == SOURCE_CANDIDATE_SHA
            else (_ for _ in ()).throw(ValueError('Invalid source'))
        ),
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def _input(**overrides):
    data = {
        'name': 'Kubespray Lab',
        'description': 'Approved source only',
        'environment': 'laboratory',
        'profile_key': PROFILE_KEY,
        'repository': REPOSITORY,
        'revision': SOURCE_CANDIDATE_SHA,
        'ansible_core_version': ANSIBLE_CORE_VERSION,
        'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
        'kubespray_release': KUBESPRAY_RELEASE,
        'execution_environment_digest': '',
    }
    return {**data, **overrides}


def test_choose_validate_save_manage_with_canonical_database(app):
    client = app.test_client()
    assert client.get('/integrations/ansible').status_code == 200
    choose = client.get('/integrations/ansible/profiles')
    assert choose.status_code == 200
    assert b'Kubernetes Lifecycle' in choose.data

    registration = client.get('/integrations/ansible/connections/new')
    assert registration.status_code == 200
    assert b'Validate Source' in registration.data
    invalid = client.post(
        '/integrations/ansible/connections/new', data={**_input(repository='evil/secret'), 'action': 'test'}
    )
    assert invalid.status_code == 200
    assert b'outside the reviewed' in invalid.data or b'does not match' in invalid.data

    checked = client.post('/integrations/ansible/connections/new', data={**_input(), 'action': 'test'})
    assert checked.status_code == 200
    match = re.search(rb'id="ansible-proof-field"[^>]*value="([^"]+)"', checked.data)
    assert match, 'source validation must render a signed proof for Save'
    token = match.group(1).decode()

    altered = client.post(
        '/integrations/ansible/connections/new',
        data={
            **_input(name='Modified'),
            'source_test_proof': token,
            'action': 'save',
        },
    )
    assert altered.status_code == 200
    assert b'Re-run Validate Source' in altered.data

    saved = client.post(
        '/integrations/ansible/connections/new',
        data={
            **_input(),
            'source_test_proof': token,
            'action': 'save',
        },
        follow_redirects=False,
    )
    assert saved.status_code == 302
    with app.app_context():
        rows = IntegrationInstance.query.filter_by(integration_type='configuration_automation').all()
        assert len(rows) == 1
        row = rows[0]
        assert row.provider_key == 'ansible'
        assert row.adapter_key == 'ansible_runner'
        assert row.enabled is False
        assert row.readiness_status == 'validation_required'
        assert row.metadata_json['source_validation']['checked_files'] == 5
        assert row.metadata_json['execution_enabled'] is False
        assert row.metadata_json['mutation_authorized'] is False
        identity = row.id

    detail = client.get(f'/integrations/ansible/connections/{identity}')
    assert detail.status_code == 200
    for expected in (
        b'Configuration',
        b'Validation &amp; Capabilities',
        b'Runtime &amp; History',
        b'Inventory &amp; Lifecycle',
        b'No committed execution history',
    ):
        assert expected in detail.data
    registry = client.get('/integrations/ansible')
    assert b'Kubespray Lab' in registry.data
    assert b'Validation Required' in registry.data
    # Reuse the existing provider-neutral navigation and detail resolver.
    orchestration = client.get('/integrations/orchestration')
    assert orchestration.status_code == 200
    assert b'Kubespray Lab' in orchestration.data
    assert f'/integrations/ansible/connections/{identity}'.encode() in orchestration.data
    provider_choose = client.get('/integrations/providers/configuration_automation')
    assert provider_choose.status_code == 200
    assert b'Ansible' in provider_choose.data
    assert b'/integrations/ansible/profiles' in provider_choose.data

    duplicate = client.post(
        '/integrations/ansible/connections/new',
        data={
            **_input(),
            'source_test_proof': token,
            'action': 'save',
        },
    )
    assert duplicate.status_code == 200
    assert b'already exists' in duplicate.data
    with app.app_context():
        assert IntegrationInstance.query.filter_by(integration_type='configuration_automation').count() == 1

    filtered = client.get(
        '/integrations/ansible?q=unknown', headers={'HX-Request': 'true', 'HX-Target': 'ansible-connection-registry'}
    )
    assert filtered.status_code == 200
    assert b'No Ansible Connections' in filtered.data
    assert b'Kubespray Lab' not in filtered.data


def test_route_permission_denial_preserves_registration_boundary(app, monkeypatch):
    principal = SimpleNamespace(
        id=2,
        is_authenticated=True,
        username='unprivileged',
        role_name='Viewer',
        has_permission=lambda _: False,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    client = app.test_client()
    for route in ('/integrations/ansible', '/integrations/ansible/profiles', '/integrations/ansible/connections/new'):
        assert client.get(route).status_code == 403
    assert client.post('/integrations/ansible/connections/new', data={**_input(), 'action': 'save'}).status_code == 403
