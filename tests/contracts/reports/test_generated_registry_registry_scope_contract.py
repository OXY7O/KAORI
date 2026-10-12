from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_scope_options_and_identity_use_existing_authority() -> None:
    src = (ROOT / 'app/reports/generated/service.py').read_text()
    assert 'get_active_registry_options()' in src
    assert "ARTIFACT_REGISTRY_INSTANCE_ASSET_TYPE}:{instance['value']}" in src
    assert "return 'Artifact Registry', 'Integration Scope'" in src
    assert 'scope = resolve_report_scope(report) if scope_asset_type != ARTIFACT_REGISTRY_INSTANCE_ASSET_TYPE else None' in src
    assert "scope_asset_label_snapshot" in src
    assert 'Registry Integration ' in src
    assert 'Report.scope_asset_type == asset_type' in src
    assert 'Report.scope_asset_id == asset_id' in src
