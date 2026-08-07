from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/kubernetes/partials/_runtime_workspace.html'


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_operational_focus_uses_clear_record_composition() -> None:
    source = _source()

    assert 'data-kaori-operational-focus' in source
    assert 'data-kaori-operational-focus-list' in source
    assert 'Prioritized evidence that needs operator review before the next controlled action.' in source
    assert "(' item' if runtime_state.attention_factors|length == 1 else ' items')" in source
    assert 'flex items-start justify-between gap-3' in source
    assert "integration_status(factor.status, display='indicator')" in source


def test_operational_focus_wraps_evidence_without_truncation() -> None:
    source = _source()

    focus = source.split('data-kaori-operational-focus', 1)[1].split('runtime-next-action-title', 1)[0]
    assert '[overflow-wrap:anywhere]' in focus
    assert 'truncate' not in focus
    assert 'No Current Runtime Attention' in focus
