"""Source contracts for concise Alertmanager registration guidance (#4698)."""

from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html"
)


def test_registration_guidance_preserves_connection_lifecycle() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "'Endpoint & Access'," in source
    assert "'Configure endpoint access, then test connectivity.'" in source
    assert 'flow_note="Registration creates identity; Full Validation gates consumer use."' in source
    assert 'alertmanager_related_description = "One Alertmanager serves multiple integrations."' in source
    assert "'Disabled connections stay stored but cannot serve consumers.'" in source


def test_registration_guidance_keeps_shared_components_and_binding_context() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "connection_validation_header.render(" in source
    assert "operational_toggle.render(" in source
    assert "provider_registration_context.render(" in source
    assert "if initial_cluster" in source
    assert "initial alert binding for " in source
    assert 'name="enabled"' in source
    assert 'name="verify_ssl"' in source
    assert "Run Full Validation" in source
