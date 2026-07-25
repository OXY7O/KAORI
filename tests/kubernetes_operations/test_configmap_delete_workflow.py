from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes_operations.configmaps import routes, service


def _target():
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7, name='Development'),
        namespace='default',
        name='application-config',
    )


def _form() -> dict[str, str]:
    return {'confirm_name': 'application-config'}


def _live_payload(resource_version: str = '101') -> dict[str, object]:
    return {
        'resource_version': resource_version,
        'data': {'key': 'value'},
        'binary_data': {},
    }


def test_delete_validation_uses_non_destructive_authorization_preflight(monkeypatch) -> None:
    target = _target()
    reviews: list[object] = []

    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'read_configmap', lambda selected: _live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])
    monkeypatch.setattr(
        service,
        '_live_call',
        lambda *args, **kwargs: pytest.fail('Validation must not call the ConfigMap DELETE endpoint.'),
    )

    authorization_api = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: (
            reviews.append(kwargs['body'])
            or SimpleNamespace(status=SimpleNamespace(allowed=True))
        )
    )
    monkeypatch.setattr(
        service,
        '_authorization_call',
        lambda cluster, operation, callback: callback(authorization_api),
    )

    result = service.delete_configmap(_form(), validate_only=True)

    assert len(reviews) == 1
    attributes = reviews[0].spec.resource_attributes
    assert attributes.resource == 'configmaps'
    assert attributes.verb == 'delete'
    assert attributes.namespace == 'default'
    assert attributes.name == 'application-config'
    assert result['operation'] == 'validation'
    assert result['validation_mode'] == 'authorization_preflight'
    assert result['resource_version'] == '101'


def test_delete_validation_rejects_missing_delete_authorization(monkeypatch) -> None:
    target = _target()

    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'read_configmap', lambda selected: _live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])

    authorization_api = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: SimpleNamespace(
            status=SimpleNamespace(allowed=False)
        )
    )
    monkeypatch.setattr(
        service,
        '_authorization_call',
        lambda cluster, operation, callback: callback(authorization_api),
    )

    with pytest.raises(ValueError, match='denied ConfigMap deletion'):
        service.delete_configmap(_form(), validate_only=True)


def test_final_delete_executes_once_without_repeating_validation(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    target = _target()

    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'read_configmap', lambda selected: _live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])
    monkeypatch.setattr(
        service,
        '_authorization_call',
        lambda *args, **kwargs: pytest.fail('Final delete must use the signed validation receipt.'),
    )

    api = SimpleNamespace(
        delete_namespaced_config_map=lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(
        service,
        '_live_call',
        lambda cluster, operation, callback: callback(api),
    )

    result = service.delete_configmap(
        _form(),
        validate_only=False,
        expected_resource_version='101',
    )

    assert len(calls) == 1
    assert 'dry_run' not in calls[0]
    assert calls[0]['name'] == 'application-config'
    assert calls[0]['namespace'] == 'default'
    assert calls[0]['body'].preconditions.resource_version == '101'
    assert result['operation'] == 'deletion'
    assert result['validation_mode'] == 'validated_receipt'


def test_final_delete_rejects_target_changed_after_validation(monkeypatch) -> None:
    target = _target()
    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'read_configmap', lambda selected: _live_payload('102'))
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])

    with pytest.raises(ValueError, match='changed after validation'):
        service.delete_configmap(
            _form(),
            validate_only=False,
            expected_resource_version='101',
        )


def test_delete_workspace_refreshes_live_options_and_removes_deleted_target(monkeypatch) -> None:
    retained = SimpleNamespace(name='retained-config')
    deleted = SimpleNamespace(name='application-config')
    context = {
        'clusters': [SimpleNamespace(id=7, name='Development')],
        'selected_cluster_id': '7',
        'selected_namespace': 'default',
        'selected_configmap_name': '',
        'selected_namespaces': ['default', 'operations'],
        'selected_configmaps': [deleted, retained],
        'selection_error': None,
        'selection_error_title': None,
    }
    calls: list[tuple[str, str, str]] = []

    def selection_context(cluster_id: str, namespace: str, configmap_name: str = ''):
        calls.append((cluster_id, namespace, configmap_name))
        return context

    monkeypatch.setattr(routes, '_selection_context', selection_context)

    refreshed = routes._refresh_delete_workspace({
        'cluster_id': 7,
        'namespace': 'default',
        'configmap_name': 'application-config',
    })

    assert calls == [('7', 'default', '')]
    assert refreshed['selected_namespace'] == 'default'
    assert [item.name for item in refreshed['selected_configmaps']] == ['retained-config']
    assert refreshed['selected_configmap_name'] == ''
