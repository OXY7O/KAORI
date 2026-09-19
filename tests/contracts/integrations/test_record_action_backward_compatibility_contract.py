from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTIONS = ROOT / 'app/templates/integrations/components/_record_actions.html'


def test_view_more_preserves_role_keyword_for_runtime_and_registry_callers():
    source = ACTIONS.read_text(encoding='utf-8')
    assert "macro view_more(dialog_id, label='View More', role='record'" in source
    assert 'data-kaori-{{ role }}-view-more' in source
    assert 'data-kaori-dialog-open' in source
    assert 'data-lucide="chevron-right"' in source
    assert '{{ table_ui.action_classes() }}' in source
