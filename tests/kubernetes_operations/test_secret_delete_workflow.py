from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from flask import Flask, session

from app.kubernetes_operations.secrets import delete_service, routes


def _target(resource_version: str = '101') -> SimpleNamespace:
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7, name='Development'),
        cluster_id='7',
        cluster_name='Development',
        namespace='default',
        name='application-secret',
        secret_type='Opaque',
        key_names=('username', 'password'),
        key_count=2,
        resource_version=resource_version,
    )


def _form() -> dict[str, str]:
    return {
        'cluster_id': '7',
        'namespace': 'default',
        'secret_name': 'application-secret',
        'target_cluster_id': '7',
        'target_namespace': 'default',
        'target_secret_name': 'application-secret',
        'confirm_name': 'application-secret',
    }


def test_delete_validation_never_calls_secret_delete_endpoint(monkeypatch) -> None:
    target = _target()
    preflights: list[object] = []

    monkeypatch.setattr(delete_service, '_bound_target', lambda form: target)
    monkeypatch.setattr(delete_service, 'get_secret_impact_context', lambda selected: [])
    monkeypatch.setattr(
        delete_service,
        '_validate_delete_authorization',
        lambda selected: preflights.append(selected),
    )
    monkeypatch.setattr(
        delete_service,
        'core_api',
        lambda cluster: pytest.fail(
            'Validation must not construct or call the Secret DELETE endpoint.'
        ),
    )

    result = delete_service.execute_secret_deletion(_form(), validate_only=True)

    assert preflights == [target]
    assert result.metadata['operation'] == 'validation'
    assert result.metadata['validation_mode'] == 'authorization_preflight'
    assert result.metadata['resource_version'] == '101'
    assert 'without sending a DELETE request' in result.message


def test_delete_authorization_preflight_targets_exact_secret(monkeypatch) -> None:
    reviews: list[object] = []
    authorization = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: (
            reviews.append(kwargs['body'])
            or SimpleNamespace(status=SimpleNamespace(allowed=True))
        )
    )

    monkeypatch.setattr(
        delete_service,
        'authorization_api',
        lambda cluster: authorization,
    )
    monkeypatch.setattr(
        delete_service,
        'tls_policy_for_cluster',
        lambda cluster: (None, False),
    )
    monkeypatch.setattr(
        delete_service,
        'weak_tls_context',
        lambda **kwargs: nullcontext(),
    )

    delete_service._validate_delete_authorization(_target())

    assert len(reviews) == 1
    attributes = reviews[0].spec.resource_attributes
    assert attributes.group == ''
    assert attributes.resource == 'secrets'
    assert attributes.verb == 'delete'
    assert attributes.namespace == 'default'
    assert attributes.name == 'application-secret'


def test_final_delete_executes_once_with_validated_resource_version(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    target = _target()
    api = SimpleNamespace(
        delete_namespaced_secret=lambda **kwargs: calls.append(kwargs)
    )

    monkeypatch.setattr(delete_service, '_bound_target', lambda form: target)
    monkeypatch.setattr(delete_service, 'get_secret_impact_context', lambda selected: [])
    monkeypatch.setattr(delete_service, 'core_api', lambda cluster: api)
    monkeypatch.setattr(
        delete_service,
        '_validate_delete_authorization',
        lambda selected: pytest.fail(
            'Final delete must use the signed validation receipt, not rerun preflight.'
        ),
    )
    monkeypatch.setattr(
        delete_service,
        'tls_policy_for_cluster',
        lambda cluster: (None, False),
    )
    monkeypatch.setattr(
        delete_service,
        'weak_tls_context',
        lambda **kwargs: nullcontext(),
    )

    result = delete_service.execute_secret_deletion(
        _form(),
        validate_only=False,
        expected_resource_version='101',
    )

    assert len(calls) == 1
    assert 'dry_run' not in calls[0]
    assert calls[0]['name'] == 'application-secret'
    assert calls[0]['namespace'] == 'default'
    assert calls[0]['body'].preconditions.resource_version == '101'
    assert result.metadata['operation'] == 'deletion'
    assert result.metadata['validation_mode'] == 'validated_receipt'


def test_final_delete_rejects_resource_version_drift(monkeypatch) -> None:
    monkeypatch.setattr(
        delete_service,
        '_bound_target',
        lambda form: _target(resource_version='102'),
    )
    monkeypatch.setattr(delete_service, 'get_secret_impact_context', lambda selected: [])

    with pytest.raises(ValueError, match='changed after validation'):
        delete_service.execute_secret_deletion(
            _form(),
            validate_only=False,
            expected_resource_version='101',
        )


def test_delete_receipt_is_signed_session_bound_and_target_bound() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'

    with app.test_request_context('/'):
        token = routes._issue_secret_delete_receipt(
            {
                'cluster_id': '7',
                'namespace': 'default',
                'secret_name': 'application-secret',
                'resource_version': '101',
            }
        )

        receipt = routes._verify_secret_delete_receipt(
            {
                'delete_validation_token': token,
                'cluster_id': '7',
                'namespace': 'default',
                'secret_name': 'application-secret',
            }
        )

        assert receipt == {'resource_version': '101'}
        assert session[routes._SECRET_DELETE_RECEIPT_SESSION_KEY] == token

        with pytest.raises(ValueError, match='selected Secret changed'):
            routes._verify_secret_delete_receipt(
                {
                    'delete_validation_token': token,
                    'cluster_id': '7',
                    'namespace': 'default',
                    'secret_name': 'different-secret',
                }
            )
