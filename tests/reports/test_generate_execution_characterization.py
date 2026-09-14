from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import UserMixin
from werkzeug.datastructures import MultiDict

from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import db, login_manager
from app.extensions import login as login_extension
from app.models.report import Report
from app.reports.generate import routes as generate_routes
from app.reports.generate import service as generate_service


class ReportsGenerateUser(UserMixin):
    id = 81
    username = 'reports-generate-route-test'
    display_label = 'Reports Generate Route Test'
    role_name = 'reports_generate_test'
    role_display_name = 'Reports Generate Test'
    timezone = 'UTC'
    timezone_mode = 'manual'
    locale = 'en-US'
    date_format = 'day_month_year'
    time_format = '24h'

    def __init__(self, permissions: set[str]) -> None:
        self.permissions = permissions

    def get_id(self) -> str:
        return f'reports-generate-{len(self.permissions)}'

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions


def _empty_navigation_context() -> dict[str, object]:
    return {
        'items': [],
        'history_items': [],
        'attention_items': [],
        'active_jobs': [],
        'active_count': 0,
        'attention_count': 0,
        'unread_count': 0,
        'total_count': 0,
        'display_limit': 8,
        'job_display_limit': 6,
    }


def _cluster_context() -> dict[str, object]:
    return {
        'show_banner': False,
        'is_kubernetes_scope': False,
        'is_blocked': False,
        'has_clusters': False,
        'cluster_count': 0,
        'can_manage_clusters': False,
        'database_ready': True,
    }


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        login_extension,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=True),
    )
    monkeypatch.setattr(bootstrap_presentation, 'build_cluster_onboarding_context', _cluster_context)
    monkeypatch.setattr(
        bootstrap_presentation,
        'get_navigation_notification_context',
        lambda **_kwargs: _empty_navigation_context(),
    )
    monkeypatch.setattr(bootstrap_presentation, 'pop_operational_feedback', lambda: None)
    return create_app('testing')


def _client_for_user(app, monkeypatch: pytest.MonkeyPatch, user: ReportsGenerateUser):
    monkeypatch.setattr(login_manager, '_user_callback', lambda _user_id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = user.get_id()
        session['_fresh'] = True
        session['auth_source'] = 'database'
    return client


def test_generate_route_denies_user_without_reports_generate_permission(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, ReportsGenerateUser(set()))

    def unexpected_form_read(_form):
        raise AssertionError('Generate form processing must not run before reports.generate authorization')

    monkeypatch.setattr(generate_routes, 'get_form_state_from_form', unexpected_form_read)

    response = client.get('/reports/generate')

    assert response.status_code == 403


def test_generate_route_allows_user_with_reports_generate_permission(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_for_user(app, monkeypatch, ReportsGenerateUser({'reports.generate'}))
    monkeypatch.setattr(generate_routes, 'get_form_state_from_form', lambda _form: {})
    monkeypatch.setattr(generate_routes, 'get_generate_report_payload', lambda **_kwargs: {})
    monkeypatch.setattr(generate_routes, 'render_template', lambda *_args, **_kwargs: 'reports-generate-authorized')

    response = client.get('/reports/generate')

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'reports-generate-authorized'


def test_create_report_request_commits_record_for_fresh_session_readback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_app = Flask('reports-generate-persistence-test')
    database_path = tmp_path / 'reports-generate.db'
    persistence_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(persistence_app)

    form_state = {
        'name': 'Reports Generate Persistence Evidence',
        'report_type': 'execution_characterization',
        'cluster_id': '',
        'object_storage_system_id': '',
        'namespace': '',
        'period': '30d',
        'output_format': 'csv',
        'sections': ['inventory_assets'],
    }
    report_spec = SimpleNamespace(
        requires_cluster=False,
        domain='characterization',
        source_kind='characterization',
        scope_asset_type='characterization_scope',
    )

    monkeypatch.setattr(generate_service, 'get_form_state_from_form', lambda _form: form_state)
    monkeypatch.setattr(generate_service, 'validate_form_state', lambda _form_state: [])
    monkeypatch.setattr(generate_service, 'get_report_storage_backend_status', lambda: {'write_available': True})
    monkeypatch.setattr(generate_service, 'get_report_type_spec', lambda _report_type: report_spec)

    with persistence_app.app_context():
        Report.__table__.create(db.engine)
        try:
            success, errors, report = generate_service.create_report_request(MultiDict(), user_id=None)

            assert success is True
            assert errors == []
            assert report is not None
            report_id = report.id
            assert report_id is not None

            db.session.remove()
            persisted = db.session.get(Report, report_id)

            assert persisted is not None
            assert persisted.name == 'Reports Generate Persistence Evidence'
            assert persisted.report_type == 'execution_characterization'
            assert persisted.status == 'requested'
            assert persisted.sections == ['inventory_assets']
        finally:
            db.session.remove()
            Report.__table__.drop(db.engine)
