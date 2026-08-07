from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/integrations/kubernetes/partials/_runtime_workspace.html"


def _source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_runtime_workspace_uses_decision_side_panel_layout():
    source = _source()
    assert "data-kaori-runtime-workspace-v5" in source
    assert "data-kaori-runtime-main-layout" in source
    assert "lg:grid-cols-[minmax(0,1fr)_22rem]" in source
    assert "data-kaori-runtime-decision-panel" in source
    assert "Runtime Decision" in source
    assert "Next Operational Action" in source


def test_runtime_snapshot_separates_runtime_and_validation_evidence():
    source = _source()
    assert "Runtime Snapshot" in source
    assert "Persisted Runtime Posture" in source
    assert "Validation Readiness" in source
    assert "Runtime health is sourced only from persisted observations" in source
    assert "Runtime Not Observed" in source


def test_runtime_diagnostics_follow_kaori_label_roles():
    source = _source()
    assert "Diagnostic Evidence" in source
    assert "table_label.metadata_label((runtime_state.diagnostics|length) ~ ' checks')" in source
    assert "integration_status(item.status, display='indicator')" in source
    assert "hover:bg-kaori-mist" in source


def test_runtime_identity_icons_use_kaori_brand_palette():
    source = _source()
    for marker in [
        "palette_icon('activity', 'brand'",
        "palette_icon('stethoscope', 'brand'",
        "palette_icon('gauge', 'brand'",
        "palette_icon('target', 'brand'",
    ]:
        assert marker in source


def test_runtime_observation_boundary_remains_explicit():
    source = _source()
    assert "data-kaori-runtime-observation-boundary" in source
    assert "Runtime Refresh records lightweight reachability and health evidence" in source
    assert "effective RBAC remain owned by Full Validation" in source
