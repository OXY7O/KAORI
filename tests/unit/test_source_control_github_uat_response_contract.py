"""Concrete UAT response and safe query-forwarding contracts."""

from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, Response

from app.integrations.source_control.source_control.providers.github.application import uat_routes


@pytest.fixture
def app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.register_blueprint(uat_routes.github_uat_bp)
    return flask_app


def test_detail_redirect_keeps_local_path_and_existing_inventory_filters(app: Flask) -> None:
    with app.test_request_context(
        '/?inventory_search=team+repo&inventory_archived=active&per_page=5&_external=https://untrusted.test'
    ):
        target = uat_routes._detail_url(17)

    parsed = urlsplit(target)
    params = parse_qs(parsed.query)
    assert parsed.scheme == ''
    assert parsed.netloc == ''
    assert parsed.path.endswith('/installations/17')
    assert params['inventory_search'] == ['team repo']
    assert params['inventory_archived'] == ['active']
    assert params['per_page'] == ['5']
    assert params['_external'] == ['https://untrusted.test']


@pytest.mark.parametrize('view', ['jobs', 'deliveries'])
def test_runtime_redirect_overrides_tab_without_losing_other_filters(app: Flask, view: str) -> None:
    with app.test_request_context('/?tab=inventory&runtime_view=other&query=review'):
        target = uat_routes._detail_url(17, tab='runtime', runtime_view=view)

    params = parse_qs(urlsplit(target).query)
    assert params == {'tab': ['runtime'], 'runtime_view': [view], 'query': ['review']}


def test_concrete_response_retains_no_store_headers(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uat_routes, 'render_template', lambda *_args, **_kwargs: 'committed view')

    with app.test_request_context('/'):
        response = uat_routes._response('example.html')

    assert isinstance(response, Response)
    assert response.get_data(as_text=True) == 'committed view'
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'
    assert response.headers['Pragma'] == 'no-cache'


def test_rejected_edit_returns_http_409(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uat_routes, 'render_template', lambda *_args, **_kwargs: 'review')

    with app.test_request_context('/', method='POST'):
        response = uat_routes._render_github_edit_connection_result(
            installation=SimpleNamespace(),
            canonical=SimpleNamespace(),
            form=SimpleNamespace(errors={}),
            inline_test=False,
            test_proof=None,
            message='Not accepted',
            rejection=True,
        )

    assert response.status_code == 409
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'


def test_inline_connection_proof_still_emits_hx_trigger(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uat_routes, 'render_template', lambda *_args, **_kwargs: 'proof checked')

    with app.test_request_context('/', method='POST'):
        response = uat_routes._render_github_edit_connection_result(
            installation=SimpleNamespace(),
            canonical=SimpleNamespace(),
            form=SimpleNamespace(errors={}),
            inline_test=True,
            test_proof='bounded-proof',
            message='Verified',
            rejection=False,
        )

    assert response.status_code == 200
    assert json.loads(response.headers['HX-Trigger']) == {
        'github-connection-tested': {'connected': True, 'proof': 'bounded-proof'}
    }


@pytest.mark.parametrize('active', [True, False])
def test_sync_post_returns_partial_without_redirect(app: Flask, monkeypatch: pytest.MonkeyPatch, active: bool) -> None:
    installation = SimpleNamespace(id=17, integration_instance_id=21)
    job = SimpleNamespace(is_terminal=not active)
    monkeypatch.setattr(uat_routes, '_installation_or_404', lambda _identity: installation)
    monkeypatch.setattr(uat_routes, 'current_user', SimpleNamespace(id=1))
    monkeypatch.setattr(uat_routes, 'FlaskForm', lambda: SimpleNamespace(validate_on_submit=lambda: True))
    monkeypatch.setattr(uat_routes, 'enqueue_source_repository_sync', lambda **_kwargs: (job, True))
    monkeypatch.setattr(uat_routes, 'record_operational_activity', lambda **_kwargs: None)

    def render(record, **kwargs):
        assert record is installation
        assert kwargs['sync_job'] is job
        assert kwargs['refresh_registry'] is not active
        assert kwargs['sync_blocked'] is False
        return Response('inventory partial')

    monkeypatch.setattr(uat_routes, '_render_inventory_content', render)
    with app.test_request_context('/', method='POST', headers={'HX-Request': 'true'}):
        result = uat_routes.synchronize.__wrapped__(17)
    assert result.status_code == 200
    assert result.get_data(as_text=True) == 'inventory partial'
    assert 'Location' not in result.headers
    assert 'kaori:notifications-changed' in result.headers['HX-Trigger']


def test_inventory_post_context_preserves_current_registry_selection(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    def read(**kwargs):
        assert kwargs == {
            'authorized_installation_id': 17,
            'page': 3,
            'per_page': 10,
            'search': 'team',
            'visibility': 'private',
            'archived': 'active',
        }
        return object()

    monkeypatch.setattr(uat_routes, 'read_installation_inventory_for_current_session', read)
    with app.test_request_context('/', method='POST', data={
        'page': '3', 'per_page': '10', 'inventory_search': 'team',
        'inventory_visibility': 'private', 'inventory_archived': 'active',
    }):
        context = uat_routes._inventory_context(SimpleNamespace(id=17))
    assert context['inventory_search'] == 'team'
    assert context['inventory_visibility'] == 'private'


def test_sync_poll_rejects_missing_or_foreign_job(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    from werkzeug.exceptions import NotFound

    installation = SimpleNamespace(id=17)
    monkeypatch.setattr(uat_routes, '_installation_or_404', lambda _identity: installation)

    def scoped_job(record, *, job_id):
        assert record is installation and job_id == 81
        return None

    monkeypatch.setattr(uat_routes, '_repository_sync_job', scoped_job)
    with app.test_request_context('/', headers={'HX-Request': 'true'}), pytest.raises(NotFound):
        uat_routes.synchronize_status.__wrapped__(17, 81)
