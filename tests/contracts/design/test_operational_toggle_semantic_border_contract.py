from pathlib import Path


def test_operational_toggle_uses_shared_semantic_border_authority() -> None:
    template = Path('app/templates/components/operational_toggle.html').read_text()

    assert '{% import "components/table_label.html" as table_label %}' in template
    assert "table_label.tone_border_classes('warning')" in template
    assert "table_label.tone_border_classes('critical')" in template
    assert "table_label.tone_border_classes('info')" in template

    for direct_border in (
        'border-status-warning-border',
        'border-status-critical-border',
        'border-status-info-border',
    ):
        assert direct_border not in template
