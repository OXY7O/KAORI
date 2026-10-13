from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import UserMixin
from werkzeug.datastructures import MultiDict

import app.reports.generate.routes as generate_routes
import app.reports.generate.service as generate_service
import app.reports.generated.service as generated_service
import app.reports.repository as report_repository
from app import create_app
from app.bootstrap import presentation as bootstrap_presentation
from app.extensions import db, login_manager
from app.extensions import login as login_extension
from app.models.report import Report


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


def test_scope_readiness_honors_scope_contract_without_stale_inventory_counts() -> None:
    assert generate_service._scope_is_ready(
        {'cluster_id': '', 'object_storage_system_id': ''},
        {'scope_asset_type': 'characterization_scope', 'requires_cluster': False},
    )
    assert not generate_service._scope_is_ready(
        {'cluster_id': '', 'object_storage_system_id': ''},
        {'scope_asset_type': 'kubernetes_cluster', 'requires_cluster': True},
    )
    assert generate_service._scope_is_ready(
        {'cluster_id': 'cluster-1', 'object_storage_system_id': ''},
        {'scope_asset_type': 'kubernetes_cluster', 'requires_cluster': True},
    )
    assert not generate_service._scope_is_ready(
        {'cluster_id': '', 'object_storage_system_id': ''},
        {'scope_asset_type': 'object_storage_system', 'requires_cluster': False},
    )
    assert generate_service._scope_is_ready(
        {'cluster_id': '', 'object_storage_system_id': 'storage-1'},
        {'scope_asset_type': 'object_storage_system', 'requires_cluster': False},
    )


def test_report_storage_unavailable_does_not_persist_request(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UAT-RPT-003: reject unavailable artifact storage before any report write."""
    persistence_app = Flask('reports-storage-unavailable-test')
    persistence_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{tmp_path / "reports-storage-block.db"}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(persistence_app)

    form_state = {
        'name': 'Rejected While Artifact Storage Is Unavailable',
        'report_type': 'execution_characterization',
        'cluster_id': '',
        'namespace': '',
        'object_storage_system_id': '',
        'period': '30d',
        'output_format': 'csv',
        'sections': ['inventory_assets'],
    }
    monkeypatch.setattr(generate_service, 'get_form_state_from_form', lambda _form: form_state)
    monkeypatch.setattr(generate_service, 'validate_form_state', lambda _state: [])
    checked: list[str] = []

    def unavailable_storage() -> dict[str, bool]:
        checked.append('storage')
        return {'write_available': False}

    def unexpected_report_spec(_report_type: str) -> None:
        raise AssertionError('Invalid storage readiness must stop before report creation')

    monkeypatch.setattr(generate_service, 'get_report_storage_backend_status', unavailable_storage)
    monkeypatch.setattr(generate_service, 'get_report_type_spec', unexpected_report_spec)

    with persistence_app.app_context():
        Report.__table__.create(db.engine)
        try:
            success, errors, report = generate_service.create_report_request(MultiDict(), user_id=None)

            assert success is False
            assert report is None
            assert checked == ['storage']
            assert len(errors) == 1
            assert 'Artifact storage is unavailable' in errors[0]
            assert db.session.query(Report).count() == 0
            assert not db.session.new
        finally:
            db.session.remove()
            Report.__table__.drop(db.engine)


def test_report_enqueue_failure_records_failed_outcome_and_never_claims_queued(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UAT-RPT-003: real authenticated HTTP POST maps failed dispatch to failure evidence."""
    user = ReportsGenerateUser({'reports.generate'})
    client = _client_for_user(app, monkeypatch, user)
    report = SimpleNamespace(
        id=42,
        name='Controlled queue failure',
        report_type='inventory_overview',
    )
    creation_calls: list[int] = []
    marked_failed: list[tuple[int, str]] = []
    activity: list[dict[str, object]] = []

    def admitted_request(_form, user_id):
        creation_calls.append(user_id)
        return True, [], report

    def rejected_dispatch(_report, *, requested_by_user_id, trigger_type):
        assert requested_by_user_id == user.id
        assert trigger_type == 'manual'
        raise generate_routes.ReportJobEnqueueError('isolated worker unavailable')

    monkeypatch.setattr(generate_routes, 'create_report_request', admitted_request)
    monkeypatch.setattr(generate_routes, 'enqueue_report_generation', rejected_dispatch)
    monkeypatch.setattr(
        generate_routes,
        'mark_report_queue_failure',
        lambda report_id, *, message: marked_failed.append((report_id, message)),
    )
    monkeypatch.setattr(
        generate_routes,
        'record_operational_activity',
        lambda **kwargs: activity.append(kwargs),
    )
    monkeypatch.setattr(
        generate_routes,
        'build_report_reference',
        lambda _report: 'KAORI-TEST-QUEUE-FAILURE',
    )

    response = client.post('/reports/generate', data={'name': report.name}, follow_redirects=False)

    assert response.status_code == 302
    assert f'/reports/generated/{report.id}' in response.headers['Location']
    assert creation_calls == [user.id]
    assert len(marked_failed) == 1
    assert marked_failed[0][0] == report.id
    assert 'could not queue' in marked_failed[0][1].lower()
    assert len(activity) == 1
    assert activity[0]['event_type'] == 'report_generation_queue_failed'
    assert activity[0]['status'] == 'error'
    assert activity[0]['title'] == 'Report Not Queued'
    assert activity[0]['metadata'] == {
        'report_id': report.id,
        'report_name': report.name,
        'report_type': report.report_type,
        'feedback_delivery': 'toast',
    }


def test_queued_report_failure_persists_failed_detail_without_pending_poll(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UAT-RPT-003: durable failed Report is not rendered as queued/ready evidence."""
    persistence_app = Flask('reports-queue-failure-detail-test')
    persistence_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{tmp_path / "reports-queue-failed-detail.db"}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(persistence_app)

    with persistence_app.app_context():
        Report.__table__.create(db.engine)
        try:
            report = Report()
            report.name = 'Isolated failed generation'
            report.report_type = 'execution_characterization'
            report.output_format = 'csv'
            report.status = 'requested'
            report.sections = ['inventory_assets']
            db.session.add(report)
            db.session.commit()
            report_id = report.id
            assert report_id is not None

            error_text = 'KAORI could not queue this report; inspect worker readiness.'
            report_repository.mark_report_queue_failure(report_id, message=error_text)
            db.session.remove()

            persisted = db.session.get(Report, report_id)
            assert persisted is not None
            assert persisted.status == 'failed'
            assert persisted.error_message == error_text
            assert persisted.job_execution_id is None
            assert persisted.file_path is None
            assert persisted.file_size_bytes is None

            monkeypatch.setattr(generated_service, '_get_cluster_map', lambda _reports: {})
            monkeypatch.setattr(generated_service, '_get_user_map', lambda _reports: {})

            def serialize_failed_detail(row, _clusters, _users):
                return {
                    'status': row.status,
                    'error_message': row.error_message,
                    'artifact_access': {'available': False},
                }

            monkeypatch.setattr(generated_service, '_serialize_report_detail', serialize_failed_detail)
            monkeypatch.setattr(
                generated_service,
                'get_report_artifact_access_notice',
                lambda _row, _access: 'Artifact unavailable after a queue failure.',
            )

            payload = generated_service.get_report_detail_payload(report_id)
            assert payload['report']['status'] == 'failed'
            assert payload['report']['error_message'] == error_text
            assert payload['job_execution'] is None
            assert payload['poll_interval_seconds'] is None
            assert 'unavailable' in payload['artifact_access_notice'].lower()
        finally:
            db.session.remove()
            Report.__table__.drop(db.engine)
