from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_record_view_more_uses_compact_kaori_table_action() -> None:
    for relative in (
        "analytics/alerts/partials/_alerts_table_row.html",
        "analytics/alerts/partials/_anomalies_table_row.html",
    ):
        content = _read(relative)
        assert 'components/table.html' in content
        assert 'table_ui.action_classes()' in content
        assert 'w-full shrink-0 sm:w-auto' in content


def test_source_readiness_shows_snapshot_metadata_only_for_materialized_data() -> None:
    source = _read("analytics/alerts/partials/_source_status.html")

    assert 'uses_snapshot_delivery = materialization and materialization.dataset_key' in source
    assert '{% if uses_snapshot_delivery %}' in source
    assert 'Alert Data Snapshot' in source
    assert 'Updated' in source
    assert 'Refresh Due' in source
    assert 'Worker Attempt' in source
    assert 'filters do not query Alertmanager or Prometheus directly' in source


def test_silence_and_ownership_use_divided_workspaces_not_card_grids() -> None:
    silence = _read("analytics/alerts/partials/_silence_inhibition_summary.html")
    ownership = _read("analytics/alerts/partials/_ownership_summary.html")

    assert 'grid divide-y divide-outline-subtle' in silence
    assert 'Inhibition Policy Readiness' in silence
    assert 'Active Silence Records' in silence
    assert 'Coverage Score' in ownership
    assert 'Runbook Coverage' in ownership
    assert 'Metadata Gaps' in ownership
    assert 'xl:grid-cols-4' not in ownership


def test_recommendations_use_operational_rows_and_semantic_priority_labels() -> None:
    recommendations = _read("analytics/alerts/partials/_recommendations.html")

    assert 'divide-y divide-outline-subtle' in recommendations
    assert 'priority_tone' in recommendations
    assert 'table_label.status_label(recommendation.priority' in recommendations
    assert 'table_ui.action_classes()' in recommendations
    assert 'recommendation.icon_class' not in recommendations
    assert 'recommendation.priority_class' not in recommendations
    assert 'lg:grid-cols-2 xl:grid-cols-3' not in recommendations
