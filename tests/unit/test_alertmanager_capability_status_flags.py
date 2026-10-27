"""Alertmanager uses the approved shared capability registry status flags."""

from types import SimpleNamespace

from app.integrations.capability_registry import CapabilityStatusFlags
from app.integrations.observability.alert_source.providers.alertmanager.application import workspace_web


def test_alertmanager_optional_capability_is_classified_without_legacy_keyword(monkeypatch) -> None:
    rows = [
        {'label': 'Required Capability', 'required': True, 'available': True},
        {'label': 'Optional Capability', 'required': False, 'available': False},
    ]
    monkeypatch.setattr(
        workspace_web,
        'build_instance_context',
        lambda *_args, **_kwargs: {'capability_rows': rows, 'bindings': []},
    )
    monkeypatch.setattr(workspace_web, '_active_task', lambda *_args: None)
    monkeypatch.setattr(workspace_web, '_active_binding_task', lambda *_args: None)

    recorded: dict[str, object] = {}
    original = workspace_web.build_capability_registry_view

    def capture(source_rows, **kwargs):
        recorded.update(kwargs)
        return original(source_rows, **kwargs)

    monkeypatch.setattr(workspace_web, 'build_capability_registry_view', capture)
    context = workspace_web.instance_context(SimpleNamespace(integration_instance_id=21))

    assert len(context['capability_registry']['rows']) == 2
    assert recorded['status_flags'] == CapabilityStatusFlags(optional_gap=True)
    filtered = original(rows, status_flags=recorded['status_flags'], status='optional_gap')
    assert filtered['rows'] == [rows[1]]
