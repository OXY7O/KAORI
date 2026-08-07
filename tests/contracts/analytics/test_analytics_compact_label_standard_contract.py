from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ANALYTICS = ROOT / 'app/templates/analytics'


def read(relative: str | Path) -> str:
    path = relative if isinstance(relative, Path) else ROOT / relative
    return path.read_text(encoding='utf-8')


def test_analytics_compact_label_verifier_is_release_gated() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    verifier = read('scripts/verify_analytics_compact_label_standard.py')

    assert 'verify_analytics_compact_label_standard.py' in quality_gate
    assert 'Analytics status_label must not pass a Lucide icon' in verifier
    assert 'page-local compact label markup is forbidden' in verifier
    assert 'count/category metadata must stay iconless' in verifier


def test_capacity_pressure_status_is_text_first_and_keeps_semantic_icon_outside_label() -> None:
    pressure_lane = read('app/templates/analytics/components/_resource_pressure_lane.html')

    assert "table_label.status_label(resolved_status, resolved_tone, size='compact')" in pressure_lane
    assert "status_label(resolved_status, resolved_tone, resolved_icon" not in pressure_lane
    assert "icon=resolved_icon" in pressure_lane
    assert "role='status'" in pressure_lane


def test_dense_analytics_record_states_use_semantic_dots() -> None:
    alerts = read('app/templates/analytics/alerts/partials/_alerts_table_row.html')
    workloads = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')
    quotas = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/storage/partials/_persistent_volumes_panel.html')

    assert "status_indicator_label(alert.status|title" in alerts
    assert 'status_indicator_label(row.configuration_status.label' in workloads
    assert 'status_indicator_label(row.metrics_coverage.label' in workloads
    assert 'status_indicator_label(row.quota_status.label' in quotas
    assert 'status_indicator_label(row.status' in pvc
    assert 'status_indicator_label(row.status' in pv


def test_analytics_has_no_page_local_compact_label_bundle() -> None:
    for path in ANALYTICS.rglob('*.html'):
        source = path.read_text(encoding='utf-8')
        assert 'text-[10px]' not in source, path
        assert 'text-[11px]' not in source, path
        assert not (
            'inline-flex' in source
            and 'min-h-6' in source
            and 'rounded-md' in source
            and 'table_label.html' not in path.as_posix()
        ), path
