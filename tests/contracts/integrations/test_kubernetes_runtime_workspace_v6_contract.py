from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/integrations/kubernetes/partials/_runtime_workspace.html"


def _source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_runtime_workspace_uses_balanced_decision_side_panel_layout():
    source = _source()
    assert "data-kaori-runtime-workspace-v6" in source
    assert "data-kaori-runtime-main-layout" in source
    assert "lg:grid-cols-[minmax(0,1fr)_23rem]" in source
    assert "data-kaori-runtime-decision-panel" in source
    assert "Runtime Decision" in source
    assert "Next Operational Action" in source


def test_runtime_snapshot_has_no_placeholder_grid_gap():
    source = _source()
    assert "data-kaori-runtime-snapshot-layout" in source
    assert "lg:grid-cols-[minmax(0,1.35fr)_minmax(19rem,0.65fr)]" in source
    assert "data-kaori-runtime-observation-context" in source
    assert "Diagnostic Coverage" in source
    assert "sm:col-span-2 xl:col-span-1" not in source


def test_runtime_snapshot_separates_runtime_and_validation_evidence():
    source = _source()
    assert "Runtime Snapshot" in source
    assert "Persisted Runtime Posture" in source
    assert "Validation Readiness" in source
    assert "Runtime health is sourced only from persisted observations" in source
    assert "Runtime Not Observed" in source


def test_runtime_diagnostics_use_stable_twelve_column_layout():
    source = _source()
    assert "Diagnostic Evidence" in source
    assert "md:grid-cols-12" in source
    assert "md:col-span-3" in source
    assert "md:col-span-7" in source
    assert "md:col-span-2" in source
    assert "integration_status(item.status, display='indicator')" in source
    assert "hover:bg-kaori-mist" in source


def test_runtime_observation_boundary_is_integrated_with_diagnostics():
    source = _source()
    assert '<footer class="border-t border-outline-subtle bg-surface-subtle' in source
    assert "data-kaori-runtime-observation-boundary" in source
    assert "Runtime Refresh records lightweight reachability and health evidence" in source
    assert "effective RBAC remain owned by Full Validation" in source


def test_runtime_decision_focuses_on_evidence_ownership_and_lifecycle():
    source = _source()
    assert "Current Runtime Gate" in source
    assert "Evidence Ownership" in source
    assert "Runtime Refresh" in source
    assert "Full Validation" in source
    assert "Lifecycle Contract" in source
    assert "Operational Focus" in source


def test_runtime_identity_icons_use_kaori_brand_palette():
    source = _source()
    for marker in [
        "palette_icon('activity', 'brand'",
        "palette_icon('stethoscope', 'brand'",
        "palette_icon('gauge', 'brand'",
        "palette_icon('target', 'brand'",
    ]:
        assert marker in source
