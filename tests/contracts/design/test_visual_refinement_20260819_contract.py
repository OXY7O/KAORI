from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operational_callout_actions_no_longer_compress_description_copy() -> None:
    source = read('app/templates/components/operational_callout.html')

    assert 'rounded-xl border' in source
    assert 'min-w-0 flex-1' in source
    assert 'sm:flex-row sm:items-start sm:justify-between' in source
    assert 'mt-2 text-xs leading-5' in source
    assert 'inline-flex min-h-9 shrink-0 items-center justify-center gap-2 rounded-lg border' in source


def test_detail_rows_use_more_readable_value_emphasis_for_inventory_drawers() -> None:
    source = read('app/templates/components/details/_detail_content.html')

    assert 'sm:grid-cols-[minmax(9rem,0.42fr)_minmax(0,1fr)]' in source
    assert 'text-left text-sm font-semibold leading-5 text-content-primary' in source


def test_workload_mapping_modal_uses_investigation_width_and_bar_reading_guide() -> None:
    source = read('app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html')

    assert "size='investigation'" in source
    assert 'xl:grid-cols-[repeat(3,minmax(0,1fr))_minmax(15rem,1.15fr)]' in source
    assert 'sm:whitespace-nowrap' in source
    assert 'How To Read The Bars' in source
    assert 'Green stays below 75%' in source
    assert "table_label.status_label('Below 75%', 'normal', size='compact')" in source
    assert "table_label.status_label('75% To 90%', 'warning', size='compact')" in source
    assert "table_label.status_label('Above 90%', 'critical', size='compact')" in source
    assert 'Current vs Selected-Window Peak' in source


def test_forecast_resource_outlook_uses_clearer_threshold_timing_copy() -> None:
    source = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')

    assert (
        'md:grid-cols-[minmax(0,1.2fr)_minmax(9rem,0.85fr)_minmax(9rem,0.85fr)_minmax(12rem,1.05fr)_minmax(10rem,0.95fr)]'
        in source
    )
    assert 'Warning: {{ item.warning_eta.label }}' in source
    assert 'Critical: {{ item.critical_eta.label }}' in source
    assert 'md:flex-col md:items-start' in source
