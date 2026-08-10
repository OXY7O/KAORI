from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/kubernetes/partials/_runtime_workspace.html'


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_runtime_workspace_is_full_width_and_decision_first():
    source = _source()
    assert 'data-kaori-runtime-workspace-v8' in source
    assert 'data-kaori-runtime-main-layout' in source
    assert 'space-y-4 p-4 sm:p-5' in source
    assert 'data-kaori-runtime-decision-summary' in source
    assert 'Runtime Decision' in source
    assert 'data-kaori-runtime-decision-panel' not in source


def test_runtime_decision_has_balanced_horizontal_facts():
    source = _source()
    assert 'data-kaori-runtime-decision-facts' in source
    assert 'sm:grid-cols-2 xl:grid-cols-4' in source
    for label in ['Runtime Posture', 'Current Runtime Gate', 'Validation Readiness', 'Observation Context']:
        assert label in source
    assert 'data-kaori-runtime-primary-finding' in source
    assert 'Primary Finding' in source


def test_runtime_diagnostics_use_stable_twelve_column_layout_with_short_copy():
    source = _source()
    assert 'Diagnostic Evidence' in source
    assert 'md:grid-cols-12' in source
    assert 'md:col-span-3' in source
    assert 'md:col-span-7' in source
    assert 'md:col-span-2' in source
    assert "integration_status(item.status, display='indicator')" in source
    assert '{{ item.summary }}' in source
    assert '{{ item.recommendation }}' not in source


def test_runtime_observation_boundary_is_integrated_with_diagnostics():
    source = _source()
    assert '<footer class="border-t border-outline-subtle bg-surface-subtle' in source
    assert 'data-kaori-runtime-observation-boundary' in source
    assert 'Evidence Boundary' in source
    assert 'Runtime Refresh owns reachability, latency, and current health.' in source


def test_runtime_does_not_duplicate_lifecycle_or_operational_focus_in_decision():
    source = _source()
    assert 'Lifecycle Contract' in source
    assert source.count('Lifecycle Contract') == 1
    assert 'Operational Focus' not in source
    assert 'Evidence Ownership' not in source
    assert 'runtime_state.message' not in source
