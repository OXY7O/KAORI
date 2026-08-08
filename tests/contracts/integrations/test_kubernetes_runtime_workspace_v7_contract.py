from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/kubernetes/partials/_runtime_workspace.html'


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_primary_finding_is_compact_and_nonduplicative() -> None:
    source = _source()

    assert 'data-kaori-runtime-primary-finding' in source
    assert 'Primary Finding' in source
    assert "(' Finding' if runtime_state.attention_factors|length == 1 else ' Findings')" in source
    assert '{{ runtime_state.summary }}' in source
    assert 'data-kaori-runtime-response' in source
    assert 'Operational Response' in source
    assert 'data-kaori-runtime-next-action-card' in source
    assert 'data-kaori-runtime-evidence-handoff' in source
    finding = source.split('data-kaori-runtime-primary-finding', 1)[1].split('runtime-next-action-title', 1)[0]
    assert 'runtime_state.message' not in finding
    assert 'truncate' not in finding
    assert 'rounded-xl border border-outline-subtle bg-surface-card p-4 shadow-sm' not in finding


def test_current_page_defers_long_diagnostic_detail_to_runtime_observation_modal() -> None:
    source = _source()

    diagnostic = source.split('data-kaori-runtime-diagnostic-list', 1)[1].split('data-kaori-runtime-observation-boundary', 1)[0]
    assert '{{ item.summary }}' in diagnostic
    assert '{{ item.detail }}' not in diagnostic
    assert '{{ item.recommendation }}' not in diagnostic
    assert 'Detailed evidence and remediation are available from Recent Runtime Observations.' in source
