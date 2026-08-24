from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_kubernetes_record_tables_place_loading_bar_below_header_row() -> None:
    paths = (
        'app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html',
        'app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html',
        'app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html',
        'app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html',
    )

    for path in paths:
        source = read(path)
        assert 'data-kaori-record-header="stacked-loading"' in source, path
        assert 'border-b border-outline-subtle px-5 py-4 sm:px-6' in source, path
        assert 'loading_bar.render(' in source, path


def test_alert_and_anomaly_record_tables_are_embedded_in_workspace_surface() -> None:
    alerts = read('app/templates/kubernetes/analytics/alerts/partials/_alerts_table.html')
    anomalies = read('app/templates/kubernetes/analytics/alerts/partials/_anomalies_table.html')

    assert "evidence_list.shell('Active Alert Records', embedded=true)" in alerts
    assert "evidence_list.shell('Anomaly Candidates', embedded=true)" in anomalies


def test_object_storage_bucket_record_filters_refresh_with_htmx_without_apply_button() -> None:
    bucket_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')

    assert (
        'hx-trigger="keyup[event.target.name === \'bucket_q\'] changed delay:450ms, '
        'search[event.target.name === \'bucket_q\']"' in bucket_table
    )
    assert 'Apply Filter' not in bucket_table
    assert 'object-storage-bucket-table-loading-indicator' in bucket_table
    assert 'clear_filters_action' in bucket_table


def test_top_consumer_wording_uses_compact_guidance_and_expanded_definitions() -> None:
    section = read('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html')

    assert (
        'Compare consumption, scope contribution, denominator context, and priority without comparing unlike '
        'resource units.' in section
    )
    assert (
        'Consumption ranks the largest users; Contribution shows each consumer’s share of the selected scope; '
        'Pressure compares observed usage with available capacity.' in section
    )
    assert (
        'Compare absolute consumption, selected-scope contribution, denominator context, and operational priority '
        'without treating heterogeneous resource units as directly comparable.' not in section
    )
