"""Routing mode is a visible committed recommendation control with narrow authority."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_routing_mode_ui_is_permission_gated_and_revision_bound():
    routes = read('app/intelligence/alert_intelligence/routes.py')
    template = read('app/templates/intelligence/partials/_alert_delivery_mode.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    assert (
        "@alert_intelligence_bp.post('/routing/mode')\n"
        "@permission_required('intelligence.view')\n"
        "@permission_required('integrations.manage')"
    ) in routes
    assert "request.form.get('revision')" in routes
    assert "current_user.has_permission('integrations.manage')" in template
    assert 'name="csrf_token"' in template
    assert 'name="revision" value="{{ mode.revision }}"' in template
    assert 'type="radio" name="mode"' in template
    assert 'All Recommendation Domains' in template
    assert 'Vault provider-origin delivery has separate qualification.' in template
    assert '_alert_delivery_mode.html' in routing
    assert 'Explicit Routing Policy Required' in routing
    assert 'Recommendation Delivery Disabled' in routing


def test_recovery_and_both_generic_dispatch_paths_recheck_mode():
    service = read('app/integrations/delivery/notification_channels/service.py')
    for function in ('dispatch_alert_notification', 'dispatch_notification_event', 'recover_notification_deliveries'):
        body = service.split(f'def {function}(', 1)[1].split('\ndef ', 1)[0]
        assert 'recommendation_event_allowed(' in body
        assert body.index('recommendation_event_allowed(') < body.index('_begin_delivery_attempt(')
    assert 'Replay blocked by current alert routing mode.' in service
