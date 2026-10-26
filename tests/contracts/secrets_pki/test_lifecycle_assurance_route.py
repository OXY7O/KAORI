"""Secrets & PKI Lifecycle direct-route permission and source ownership contract."""

from pathlib import Path


import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

from app.secrets_pki import routes as secrets_pki_routes


class _Actor(UserMixin):
    def __init__(self, permissions):
        self.id = 'lifecycle-fixture'
        self.permissions = permissions

    def has_permission(self, key):
        return key in self.permissions


@pytest.fixture
def client_with_evidence(monkeypatch):
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-only-lifecycle-route', TEST_KEYS=set())
    manager = LoginManager()
    manager.init_app(app)

    @manager.user_loader
    def load_user(_uid):
        return _Actor(app.config['TEST_KEYS'])

    app.register_blueprint(secrets_pki_routes.secrets_pki_bp)
    call_args = []

    monkeypatch.setattr(secrets_pki_routes, 'build_kv2_version_posture',
                        lambda: {'status': 'incomplete_evidence', 'label': 'Not qualified'})
    monkeypatch.setattr(secrets_pki_routes, 'build_stored_pki_validity_posture',
                        lambda: {'status': 'unavailable', 'label': 'Not qualified'})
    def overlap(*, authorized_to_view_kubernetes_tls):
        call_args.append(authorized_to_view_kubernetes_tls)
        return {'status': 'source_unknown', 'label': 'Not qualified'}
    monkeypatch.setattr(secrets_pki_routes, 'build_certificate_delivery_overlap', overlap)
    monkeypatch.setattr(secrets_pki_routes, 'render_template',
                        lambda template, **_ctx: template)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = 'lifecycle-fixture'
        session['_fresh'] = True
    return app, client, call_args


@pytest.mark.parametrize('permission', [set(), {'tls_certificates.view'}, {'analytics.view'}])
def test_lifecycle_direct_route_denies_without_capability_view(client_with_evidence, permission):
    app, client, calls = client_with_evidence
    app.config['TEST_KEYS'] = permission
    response = client.get('/secrets-pki/lifecycle')
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize(('permissions', 'expected_tls'), [
    ({'secrets_pki.view'}, False),
    ({'secrets_pki.view', 'analytics.view'}, False),
    ({'secrets_pki.view', 'tls_certificates.view'}, True),
])
def test_lifecycle_cross_domain_permission_is_separate(client_with_evidence, permissions, expected_tls):
    app, client, calls = client_with_evidence
    app.config['TEST_KEYS'] = permissions
    response = client.get('/secrets-pki/lifecycle')
    assert response.status_code == 200
    assert b'secrets_pki/lifecycle.html' in response.data
    assert calls == [expected_tls]


def test_lifecycle_template_only_shows_qualified_metrics_and_safe_analytics_link():
    source = (Path(__file__).resolve().parents[3] / 'app/templates/secrets_pki/lifecycle.html').read_text()
    assert "kv2_version_posture.status in ('ready', 'observed_empty')" in source
    assert "pki_validity.status == 'ready'" in source
    assert "delivery_overlap.status == 'permission_required'" in source
    assert "{% if can_view_analytics %}" in source
    assert 'section_card.render' in source and 'metric_card.render' in source
    assert 'url_for(\'secrets_pki.inventory\')' in source
    assert "vault.secret_value" not in source
    assert "delivery_proven" not in source

def test_lifecycle_navigation_is_reachable_from_existing_capability_pages():
    root = Path(__file__).resolve().parents[3]
    for file in ('overview.html', 'inventory.html'):
        source = (root / 'app/templates/secrets_pki' / file).read_text(encoding='utf-8')
        assert "url_for('secrets_pki.lifecycle')" in source
