from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/integrations/kubernetes/partials/_runtime_workspace.html'


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_runtime_workspace_uses_horizontal_decision_summary():
    source = _source()
    assert 'data-kaori-runtime-workspace-v8' in source
    assert 'data-kaori-runtime-main-layout' in source
    assert 'data-kaori-runtime-decision-summary' in source
    assert 'data-kaori-runtime-decision-facts' in source
    assert 'Runtime Decision' in source
    assert 'Current Runtime Gate' in source
    assert 'Next Operational Action' in source
    assert 'data-kaori-runtime-decision-panel' not in source
    assert 'lg:grid-cols-[minmax(0,1fr)_23rem]' not in source


def test_runtime_decision_separates_runtime_and_validation_evidence():
    source = _source()
    assert 'Runtime Posture' in source
    assert 'Validation Readiness' in source
    assert 'Observation Context' in source
    assert 'Health gate only; validation remains independent.' in source
    assert 'Runtime Snapshot' not in source


def test_runtime_diagnostics_follow_kaori_label_roles_and_use_concise_summary():
    source = _source()
    assert 'Diagnostic Evidence' in source
    assert "table_label.metadata_label((runtime_state.diagnostics|length) ~ ' Checks')" in source
    assert "integration_status(item.status, display='indicator')" in source
    assert '{{ item.summary }}' in source
    assert '{{ item.detail }}' not in source
    assert 'hover:bg-kaori-mist' in source


def test_runtime_identity_icons_use_kaori_brand_palette():
    source = _source()
    for marker in [
        "palette_icon('gauge', 'brand'",
        "palette_icon('scan-line', 'brand'",
        "palette_icon('stethoscope', 'brand'",
        "palette_icon('target', 'brand'",
    ]:
        assert marker in source


def test_runtime_observation_boundary_remains_explicit_without_duplicate_error_copy():
    source = _source()
    assert 'data-kaori-runtime-observation-boundary' in source
    assert 'Runtime Refresh owns reachability, latency, and current health.' in source
    assert (
        'Full Validation owns API discovery, compatibility selection, capability contracts, and effective RBAC.'
        in source
    )
    assert 'runtime_state.message' not in source
