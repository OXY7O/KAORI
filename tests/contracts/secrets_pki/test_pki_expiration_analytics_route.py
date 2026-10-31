"""Direct Secrets & PKI Analytics route requires independent capability permissions."""

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

from app.secrets_pki import routes as secrets_pki_routes


class _Actor(UserMixin):
    def __init__(self, keys):
        self.keys = keys
        self.id = 'fixture-user'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.keys


@pytest.fixture
def guarded_client(monkeypatch):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-route-permission'
    app.config['TEST_PERMISSION_KEYS'] = set()
    manager = LoginManager()
    manager.init_app(app)

    @manager.user_loader
    def load_user(_user_id):
        return _Actor(app.config['TEST_PERMISSION_KEYS'])

    app.register_blueprint(secrets_pki_routes.secrets_pki_bp)
    monkeypatch.setattr(
        secrets_pki_routes,
        'build_stored_pki_validity_posture',
        lambda: {'status': 'not_configured'},
    )
    monkeypatch.setattr(
        secrets_pki_routes,
        'render_template',
        lambda template, **_context: template,
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = 'fixture-user'
        session['_fresh'] = True
    return app, client


@pytest.mark.parametrize(
    'permissions',
    [
        set(),
        {'secrets_pki.view'},
        {'analytics.view'},
    ],
)
def test_unauthorized_direct_analytics_route_fails_closed(guarded_client, permissions):
    app, client = guarded_client
    app.config['TEST_PERMISSION_KEYS'] = permissions
    response = client.get('/secrets-pki/analytics/certificates')
    assert response.status_code == 403
    assert b'certificates.html' not in response.data


def test_combined_permissions_admit_safe_snapshot_page(guarded_client):
    app, client = guarded_client
    app.config['TEST_PERMISSION_KEYS'] = {'secrets_pki.view', 'analytics.view'}
    response = client.get('/secrets-pki/analytics/certificates')
    assert response.status_code == 200
    assert b'secrets_pki/analytics/certificates.html' in response.data
