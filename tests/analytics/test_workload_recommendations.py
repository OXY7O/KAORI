from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_recommendations_deep_link_to_owning_tab_and_filter() -> None:
    source = read('app/intelligence/recommendation_engine.py')

    for href in (
        '/analytics/workload?tab=quotas&tenant_quota_status=Missing',
        '/analytics/workload?tab=quotas&tenant_quota_status=Partial',
        '/analytics/workload?tab=mapping&workload_configuration=Requests+Missing',
        '/analytics/workload?tab=mapping&workload_configuration=Requests+Partial',
        '/analytics/workload?tab=mapping&workload_qos=BestEffort',
        '/analytics/workload?tab=mapping&workload_risk=High',
        '/analytics/workload?tab=mapping&workload_risk=Medium',
    ):
        assert href in source


def test_cpu_limit_unset_is_informational_in_overview_recommendations() -> None:
    source = read('app/intelligence/recommendation_engine.py')

    assert "title='Confirm Intentional CPU Limit Policy'" in source
    assert 'is_actionable=False' in source[source.index("title='Confirm Intentional CPU Limit Policy'") :]
    assert 'missing_baseline_total = missing_cpu_requests + missing_memory_requests + memory_limits_missing' in source
    assert (
        '+ cpu_limits_unset'
        not in source[source.index('missing_baseline_total =') : source.index('if missing_baseline_total > 0:')]
    )


def test_recommendation_copy_uses_current_and_selected_window_evidence() -> None:
    source = read('app/intelligence/recommendation_engine.py')

    assert 'current and selected-window CPU and memory evidence' in source
    assert 'selected-window pod peak sums' in source
    assert 'Average Usage' not in source
