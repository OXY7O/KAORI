from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_role_form_routes_semantic_borders_through_shared_authority_red_bridge() -> None:
    form = (ROOT / 'app/templates/access/roles/form.html').read_text()

    assert 'components/operational_callout.html' in form
    assert "operational_callout.semantic_border_classes('warning')" in form
    assert "operational_callout.semantic_border_classes('critical')" in form
    assert 'border-status-warning-border' not in form
    assert 'border-status-critical-border' not in form
