"""Vault Full Validation follows the existing provider HTMX job lifecycle.

Tests isolate HTTP orchestration from Redis, Vault and real worker processes.
"""

from __future__ import annotations

from inspect import unwrap
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.integrations.secrets_management.secrets_pki.providers.vault.application import routes


def _app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='vault-validation-route-test')
    app.register_blueprint(routes.vault_bp)
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(
        routes,
        '_instance_or_404',
        lambda instance_id: SimpleNamespace(
            id=instance_id,
            integration_instance_id=99,
            enabled=True,
            readiness_status='degraded',
            capabilities=['health', 'approle', 'token_lookup'],
        ),
    )
    return app


@pytest.mark.parametrize('is_htmx', [False, True])
def test_vault_validation_uses_canonical_job_admission_with_page_fallback(
    monkeypatch: pytest.MonkeyPatch,
    is_htmx: bool,
) -> None:
    app = _app(monkeypatch)
    queued: list[dict[str, Any]] = []
    snapshot = {'task_id': 'vault-test-task', 'is_active': True}

    def enqueue(**kwargs: Any) -> tuple[dict[str, Any], bool]:
        queued.append(kwargs)
        return snapshot, True

    monkeypatch.setattr(routes, 'enqueue_instance_validation', enqueue)
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: {'template': template, **context})
    url = '/integrations/secrets-management/secrets-pki/vault/instances/15/validate'
    with app.test_request_context(
        url, method='POST', headers={'HX-Request': 'true'} if is_htmx else {}
    ):
        result = unwrap(routes.validate)(15)

    assert queued == [
        {
            'integration_type': 'secrets_pki',
            'integration_instance_id': 99,
            'requested_by_user_id': 42,
        }
    ]
    if is_htmx:
        assert isinstance(result, dict)
        assert result['template'].endswith('vault/partials/_detail_validation.html')
        assert result['validation_job'] is snapshot
        assert result['operation_feedback'] is None
    else:
        assert result.status_code == 302
        assert result.location.endswith('/instances/15#validation')


def test_vault_validation_queue_failure_reports_safe_in_place_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    reported: list[dict[str, Any]] = []

    def fail_enqueue(**kwargs: Any) -> None:
        raise RuntimeError('private provider/job error')

    def report(**kwargs: Any) -> dict[str, Any]:
        reported.append(kwargs)
        return {'title': kwargs['title'], 'status': kwargs['status']}

    monkeypatch.setattr(routes, 'enqueue_instance_validation', fail_enqueue)
    monkeypatch.setattr(routes, 'record_operational_activity', report)
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: context)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/validate',
        method='POST',
        headers={'HX-Request': 'true'},
    ):
        result = unwrap(routes.validate)(15)

    assert result['operation_feedback']['status'] == 'error'
    assert result['validation_job'] is None
    assert reported[0]['queue_feedback'] is False
    assert 'private provider/job error' not in str(reported)


def test_vault_validation_status_rejects_cross_instance_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(
        routes,
        'build_validation_snapshot',
        lambda task_id: {'task_id': task_id, 'integration_type': 'secrets_pki', 'integration_instance_id': 7},
    )
    with app.test_request_context('/'):
        with pytest.raises(NotFound):
            unwrap(routes.validation_status)(15, 'unrelated-task')


@pytest.mark.parametrize('complete', [False, True])
def test_vault_validation_status_polls_scoped_snapshot_and_signals_completion(
    monkeypatch: pytest.MonkeyPatch,
    complete: bool,
) -> None:
    app = _app(monkeypatch)
    snapshots = {
        'task_id': 'vault-test-task',
        'integration_type': 'secrets_pki',
        'integration_instance_id': 99,
        'is_active': not complete,
        'is_complete': complete,
    }
    feedback_users: list[int] = []
    monkeypatch.setattr(routes, 'build_validation_snapshot', lambda task_id: snapshots)

    def feedback(snapshot: dict[str, Any], *, user_id: int) -> dict[str, str] | None:
        feedback_users.append(user_id)
        return {'title': 'Finished', 'status': 'success'} if complete else None

    monkeypatch.setattr(routes, 'snapshot_feedback_for_user', feedback)
    monkeypatch.setattr(
        routes,
        'render_template',
        lambda template, **context: '<section id="vault-core-validation">Vault</section>',
    )
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/validation/status/vault-test-task',
        method='GET',
        headers={'HX-Request': 'true'},
    ):
        response = unwrap(routes.validation_status)(15, 'vault-test-task')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'
    assert ('HX-Trigger' in response.headers) is complete
    assert feedback_users == [42]
