from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes_operations.configmaps import service


def _target():
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7, name='Development'),
        namespace='default',
        name='application-config',
    )


def _form() -> dict[str, str]:
    return {'confirm_name': 'application-config'}


def test_delete_validation_executes_only_server_dry_run(monkeypatch) -> None:
    calls: list[str | None] = []
    target = _target()

    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(
        service,
        'read_configmap',
        lambda selected: {
            'resource_version': '101',
            'data': {'key': 'value'},
            'binary_data': {},
        },
    )
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])

    api = SimpleNamespace(
        delete_namespaced_config_map=lambda **kwargs: calls.append(kwargs['dry_run'])
    )
    monkeypatch.setattr(
        service,
        '_live_call',
        lambda cluster, operation, callback: callback(api),
    )

    result = service.delete_configmap(_form(), dry_run=True)

    assert calls == ['All']
    assert result['operation'] == 'validation'
    assert result['resource_version'] == '101'


def test_final_delete_executes_once_without_repeating_dry_run(monkeypatch) -> None:
    calls: list[str | None] = []
    target = _target()

    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(
        service,
        'read_configmap',
        lambda selected: {
            'resource_version': '101',
            'data': {'key': 'value'},
            'binary_data': {},
        },
    )
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])

    api = SimpleNamespace(
        delete_namespaced_config_map=lambda **kwargs: calls.append(kwargs['dry_run'])
    )
    monkeypatch.setattr(
        service,
        '_live_call',
        lambda cluster, operation, callback: callback(api),
    )

    result = service.delete_configmap(
        _form(),
        dry_run=False,
        expected_resource_version='101',
    )

    assert calls == [None]
    assert result['operation'] == 'deletion'


def test_final_delete_rejects_target_changed_after_validation(monkeypatch) -> None:
    target = _target()
    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(
        service,
        'read_configmap',
        lambda selected: {
            'resource_version': '102',
            'data': {},
            'binary_data': {},
        },
    )
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: [])

    with pytest.raises(ValueError, match='changed after validation'):
        service.delete_configmap(
            _form(),
            dry_run=False,
            expected_resource_version='101',
        )
