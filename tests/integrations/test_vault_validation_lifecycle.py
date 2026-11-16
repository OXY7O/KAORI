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
    with app.test_request_context(url, method='POST', headers={'HX-Request': 'true'} if is_htmx else {}):
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


def test_vault_capability_fragment_reads_only_the_registered_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    rendered: list[dict[str, Any]] = []
    instance = SimpleNamespace(id=15, readiness_status='degraded', capabilities=['health', 'approle', 'token_lookup'])
    monkeypatch.setattr(routes, '_instance_or_404', lambda instance_id: instance)

    def render(template: str, **context: Any) -> dict[str, Any]:
        rendered.append({'template': template, **context})
        return rendered[-1]

    monkeypatch.setattr(routes, 'render_template', render)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/capabilities'
        '?capability_q=token&capability_requirement=required',
        method='GET',
        headers={'HX-Request': 'true'},
    ):
        result = unwrap(routes.capability_registry)(15)

    assert result == {
        'template': 'integrations/secrets_management/vault/partials/_capability_registry.html',
        'instance': instance,
    }
    assert len(rendered) == 1
    assert instance.capabilities == ['health', 'approle', 'token_lookup']


def test_vault_runtime_history_fragment_is_scoped_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    instance = SimpleNamespace(id=15, integration_instance_id=99)
    monkeypatch.setattr(routes, '_instance_or_404', lambda instance_id: instance)
    captured: list[dict[str, Any]] = []

    def paginate(integration_type: str, instance_id: str, **filters: Any):
        captured.append({'integration_type': integration_type, 'instance_id': instance_id, **filters})
        return [], {'page': 1, 'per_page': 5, 'total_items': 0}

    monkeypatch.setattr(routes, 'paginate_runtime_history', paginate)
    monkeypatch.setattr(
        routes, 'runtime_history_view', lambda rows, *, pagination: {'rows': rows, 'pagination': pagination}
    )
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: {'template': template, **context})
    url = (
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/history'
        '?page=2&per_page=10&history_trigger=scheduled&history_health=degraded'
        '&history_readiness=degraded'
    )
    with app.test_request_context(url, method='GET', headers={'HX-Request': 'true'}):
        response = unwrap(routes.runtime_history)(15)

    assert captured == [
        {
            'integration_type': 'secrets_pki',
            'instance_id': '15',
            'page': 2,
            'per_page': 10,
            'trigger_type': 'scheduled',
            'health_status': 'degraded',
            'readiness': 'degraded',
        }
    ]
    assert response['instance'] is instance
    assert response['template'].endswith('vault/partials/_runtime_history.html')
    assert response['runtime_history']['rows'] == []


def test_vault_runtime_history_fragment_rejects_unknown_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(routes, '_instance_or_404', lambda instance_id: (_ for _ in ()).throw(NotFound()))
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/155/runtime/history'
    ):
        with pytest.raises(NotFound):
            unwrap(routes.runtime_history)(155)


@pytest.mark.parametrize('is_htmx', [False, True])
def test_vault_runtime_refresh_uses_canonical_htmx_job_admission(
    monkeypatch: pytest.MonkeyPatch,
    is_htmx: bool,
) -> None:
    app = _app(monkeypatch)
    queued: list[dict[str, Any]] = []
    snapshot = {'task_id': 'vault-runtime-task', 'operation': 'runtime_refresh', 'is_active': True}

    def enqueue(**kwargs: Any) -> tuple[dict[str, Any], bool]:
        queued.append(kwargs)
        return snapshot, True

    monkeypatch.setattr(routes, 'enqueue_runtime_health_refresh', enqueue)
    monkeypatch.setattr(
        routes, '_vault_runtime_refresh_fragment', lambda instance, **kwargs: {'instance': instance, **kwargs}
    )
    url = '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/refresh'
    with app.test_request_context(url, method='POST', headers={'HX-Request': 'true'} if is_htmx else {}):
        result = unwrap(routes.runtime_refresh)(15)

    assert queued == [
        {
            'integration_type': 'secrets_pki',
            'integration_instance_id': 99,
            'requested_by_user_id': 42,
        }
    ]
    if is_htmx:
        assert result['runtime_job'] is snapshot
        assert result['instance'].id == 15
        assert result['operation_feedback'] is None
    else:
        assert result.status_code == 302
        assert result.location.endswith('/instances/15#runtime')


def test_vault_runtime_refresh_failure_has_safe_htmx_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    recorded: list[dict[str, Any]] = []

    def fail(**kwargs: Any) -> None:
        raise RuntimeError('private provider/job secret')

    def record(**kwargs: Any) -> dict[str, Any]:
        recorded.append(kwargs)
        return {'status': kwargs['status'], 'title': kwargs['title']}

    monkeypatch.setattr(routes, 'enqueue_runtime_health_refresh', fail)
    monkeypatch.setattr(routes, 'record_operational_activity', record)
    monkeypatch.setattr(routes, '_vault_runtime_refresh_fragment', lambda instance, **kwargs: kwargs)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/refresh',
        method='POST',
        headers={'HX-Request': 'true'},
    ):
        result = unwrap(routes.runtime_refresh)(15)

    assert result['runtime_job'] is None
    assert result['operation_feedback']['status'] == 'error'
    assert recorded[0]['queue_feedback'] is False
    assert 'private provider/job secret' not in str(recorded)


def test_vault_runtime_refresh_rejects_conflicting_full_validation_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(
        routes, 'enqueue_runtime_health_refresh',
        lambda **kwargs: ({'task_id': 'validation-task', 'operation': 'full_validation'}, False),
    )
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **kwargs: {'status': kwargs['status']})
    monkeypatch.setattr(routes, '_vault_runtime_refresh_fragment', lambda instance, **kwargs: kwargs)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/refresh',
        method='POST',
        headers={'HX-Request': 'true'},
    ):
        result = unwrap(routes.runtime_refresh)(15)

    assert result['runtime_job'] is None
    assert result['operation_feedback']['status'] == 'warning'


@pytest.mark.parametrize('is_complete', [False, True])
def test_vault_runtime_status_polls_scoped_task_without_page_reload(
    monkeypatch: pytest.MonkeyPatch,
    is_complete: bool,
) -> None:
    app = _app(monkeypatch)
    snapshot = {
        'task_id': 'vault-runtime-task',
        'integration_type': 'secrets_pki',
        'integration_instance_id': 99,
        'operation': 'runtime_refresh',
        'is_active': not is_complete,
        'is_complete': is_complete,
    }
    monkeypatch.setattr(routes, 'build_validation_snapshot', lambda task_id: snapshot)
    feedback_users: list[int] = []

    def feedback(job: dict[str, Any], *, user_id: int) -> dict[str, str] | None:
        feedback_users.append(user_id)
        return {'status': 'success', 'title': 'Runtime Updated'} if is_complete else None

    monkeypatch.setattr(routes, 'snapshot_feedback_for_user', feedback)
    rendered: list[dict[str, Any]] = []

    def render(instance: Any, **kwargs: Any) -> str:
        rendered.append(kwargs)
        return '<div id="vault-runtime-content">Runtime Evidence and History</div>'

    monkeypatch.setattr(routes, '_vault_runtime_refresh_fragment', render)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/status/vault-runtime-task',
        method='GET',
        headers={'HX-Request': 'true'},
    ):
        response = unwrap(routes.runtime_refresh_status)(15, 'vault-runtime-task')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'
    assert ('HX-Trigger' in response.headers) is is_complete
    assert rendered[0]['runtime_job'] is snapshot
    assert rendered[0]['operation_feedback'] == (
        {'status': 'success', 'title': 'Runtime Updated'} if is_complete else None
    )
    assert feedback_users == [42]


@pytest.mark.parametrize(
    'integration_type,instance_id,operation',
    [
        ('secrets_pki', 77, 'runtime_refresh'),
        ('orchestration', 99, 'runtime_refresh'),
        ('secrets_pki', 99, 'full_validation'),
    ],
)
def test_vault_runtime_status_denies_cross_scope_or_wrong_operation(
    monkeypatch: pytest.MonkeyPatch,
    integration_type: str,
    instance_id: int,
    operation: str,
) -> None:
    app = _app(monkeypatch)
    monkeypatch.setattr(
        routes,
        'build_validation_snapshot',
        lambda task_id: {
            'task_id': task_id,
            'integration_type': integration_type,
            'integration_instance_id': instance_id,
            'operation': operation,
        },
    )
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/status/unrelated-task',
        headers={'HX-Request': 'true'},
    ):
        with pytest.raises(NotFound):
            unwrap(routes.runtime_refresh_status)(15, 'unrelated-task')


def test_vault_runtime_refresh_fragment_uses_only_persisted_instance_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    instance = SimpleNamespace(
        id=15,
        integration_instance_id=99,
        readiness_status='degraded',
        compatibility_profile='vault-approle-read-v1',
        capabilities=['health'],
    )
    committed = object()
    pagination = {'rows': [], 'total': 0}
    monkeypatch.setattr(routes, 'latest_vault_runtime_observation', lambda instance_id: committed)
    monkeypatch.setattr(routes, 'runtime_observation_state_view', lambda observation, **kwargs: {
        'health_status_label': 'Degraded',
        'observed_at': '2026-11-16T09:00:00+07:00',
    })
    monkeypatch.setattr(routes, '_vault_runtime_history_view', lambda instance: pagination)
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: {
        'template': template, **context,
    })
    job = {'task_id': 'runtime-task', 'is_active': True}
    with app.test_request_context('/'):
        context = routes._vault_runtime_refresh_fragment(instance, runtime_job=job)

    assert context['instance'] is instance
    assert context['latest_runtime_observation'] is committed
    assert context['runtime_state']['health_status_label'] == 'Degraded'
    assert context['runtime_history'] is pagination
    assert context['evidence']['runtime_job'] is job
    assert context['template'].endswith('vault/partials/_detail_runtime.html')

def test_vault_runtime_refresh_rejects_disabled_connection_before_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from werkzeug.exceptions import Conflict

    app = _app(monkeypatch)
    monkeypatch.setattr(
        routes,
        '_instance_or_404',
        lambda instance_id: SimpleNamespace(id=instance_id, integration_instance_id=99, enabled=False),
    )

    def unexpected_enqueue(**kwargs: Any) -> None:
        raise AssertionError('Disabled Vault instance must not enqueue runtime work')

    monkeypatch.setattr(routes, 'enqueue_runtime_health_refresh', unexpected_enqueue)
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/runtime/refresh',
        method='POST',
        headers={'HX-Request': 'true'},
    ):
        with pytest.raises(Conflict):
            unwrap(routes.runtime_refresh)(15)

