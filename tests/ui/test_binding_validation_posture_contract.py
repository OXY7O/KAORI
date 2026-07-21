from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_shared_binding_posture_component_is_used_by_both_providers():
    component = (ROOT / 'app/templates/integrations/partials/_binding_validation_posture.html').read_text()
    assert 'Source Readiness' in component
    assert 'Binding Validation' in component
    assert 'Operational Status' in component
    for relative in (
        'app/templates/prometheus/partials/_detail_scope.html',
        'app/templates/alertmanager/partials/_detail_scope.html',
    ):
        content = (ROOT / relative).read_text()
        assert '_binding_validation_posture.html' in content
        assert 'Validate Binding' in content
        assert 'status_badge(row.operational_status)' in content
