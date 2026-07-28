from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates' / 'analytics' / 'top_consumers'


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding='utf-8')


def test_summary_is_outside_the_tab_workspace_and_below_controls() -> None:
    index = _read('index.html')
    section = _read('partials/_top_consumers_section.html')

    assert '_controls_readiness.html' in index
    assert '_summary.html' in index
    assert index.index('_controls_readiness.html') < index.index('_summary.html') < index.index('_top_consumers_section.html')
    assert 'Top Consumer Summary' not in section


def test_controls_combine_filters_prometheus_and_snapshot_readiness() -> None:
    controls = _read('partials/_controls_readiness.html')

    assert 'Consumer Controls &amp; Data Readiness' in controls
    assert 'prometheus_status_panel.render' in controls
    assert 'Dataset: analytics.top_consumers' in controls
    assert 'Updated' in controls
    assert 'Worker Attempt' in controls


def test_overview_rankings_do_not_force_horizontal_scroll() -> None:
    overview = _read('partials/_top_consumers_section.html')

    assert 'Top 10 CPU Consumers' in overview
    assert 'Top 10 Memory Consumers' in overview
    assert 'overflow-x-auto' not in overview
    assert 'min-w-[' not in overview
    assert 'Capacity Share' in overview
    assert 'Total Used' in overview


def test_consumer_detail_hides_workload_pod_and_pvc_from_main_columns() -> None:
    detail = _read('partials/_consumer_detail_section.html')
    main_header = detail.split('<div class="divide-y', 1)[0]

    assert 'Workload / Pod / PVC' not in main_header
    assert 'Resource &amp; Usage' in detail
    assert "('Pod', row.pod if row.pod else '—')" in detail
    assert "identity_label = 'PVC' if row.resource_type == 'pvc' else 'Workload'" in detail
    assert 'overflow-x-auto' not in detail


def test_recommendations_use_operational_rows_and_semantic_labels() -> None:
    section = _read('partials/_top_consumers_section.html')

    assert 'Consumer Recommendations' in section
    assert "Priority: " in section
    assert "Derived From: " in section
    assert 'recommendation.icon_class' not in section
    assert 'recommendation.priority_class' not in section
    assert '<details' not in section
