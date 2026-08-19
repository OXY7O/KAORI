from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = (
    ROOT
    / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html'
)


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
    assert 'lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' not in source
    assert 'grid gap-px bg-outline-subtle lg:grid-cols-2' in source
    assert '<p class="text-xs font-semibold text-content-muted">Primary Finding</p>' in source
    assert 'class="text-xs font-semibold text-content-muted">Next Operational Action</h4>' in source
    assert 'uppercase tracking-wide' not in source
    assert 'mt-2 text-sm font-semibold leading-6 text-content-primary [overflow-wrap:anywhere]">{{ runtime_state.summary }}' in source


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
    assert 'Runtime Refresh owns reachability, latency, and current health; Full Validation owns API discovery' in source
    assert (
        'Full Validation owns API discovery, compatibility, capability contracts, and effective RBAC.'
        in source
    )
    assert 'runtime_state.message' not in source
