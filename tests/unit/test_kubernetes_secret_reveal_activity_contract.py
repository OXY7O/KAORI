"""Kubernetes Secret Reveal settings audit retains atomic and best-effort contracts."""

from types import SimpleNamespace

from app.platform_operations.kubernetes.secret_reveal import routes
from app.platform_operations.notifications.feedback import OperationalActionPresentation


def test_settings_activity_uses_durable_writer_with_action_object(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def stage(**kwargs):
        calls.append(('staged', kwargs))
        return {'writer': 'staged'}

    def record(**kwargs):
        calls.append(('best_effort', kwargs))
        return {'writer': 'best_effort'}

    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=31))
    monkeypatch.setattr(routes, 'url_for', lambda *_args, **_kwargs: '/kubernetes?tab=secret-reveal')
    monkeypatch.setattr(routes, 'stage_operational_activity', stage)
    monkeypatch.setattr(routes, 'record_operational_activity', record)

    common = {
        'event_type': 'kubernetes_secret_reveal_policy_updated',
        'status': 'success',
        'title': 'Reveal policy updated',
        'message': 'Authorized policy change was recorded.',
        'metadata': {'cluster_id': 'safe-opaque-id'},
    }
    assert routes._record_settings_activity(**common, durable_with_operation=True) == {'writer': 'staged'}
    assert calls[0][0] == 'staged'
    durable = calls[0][1]
    assert durable['action'] == OperationalActionPresentation(label='Open Kubernetes Administration', icon='server-cog')
    assert 'action_label' not in durable
    assert 'action_icon' not in durable
    assert durable['metadata']['secret_value_recorded'] is False
    assert durable['metadata']['kubeconfig_recorded'] is False

    assert routes._record_settings_activity(**common) == {'writer': 'best_effort'}
    assert calls[1][0] == 'best_effort'
    ordinary = calls[1][1]
    assert ordinary['action_label'] == 'Open Kubernetes Administration'
    assert ordinary['action_icon'] == 'server-cog'
    assert 'action' not in ordinary
    assert ordinary['metadata'] == durable['metadata']
