from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.artifact_registry.presentation_common import (
    _human_time,
    _overview_inventory_kpi_evidence,
    _registry_capacity_summary,
    _registry_consumer_insights,
    _registry_quota_watch,
    _registry_top_consumers,
)
from app.artifact_registry.presentation_overview import (
    _fleet_freshness,
    _overview_inventory_items,
    _selected_provider_freshness,
)
from app.artifact_registry.sync import (
    _mark_inventory_collection_failed,
    _mark_inventory_collection_started,
)


def _state(*, committed: bool, error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        status='ready' if committed else 'not_collected',
        last_committed_at=datetime(2026, 10, 5, tzinfo=UTC) if committed else None,
        last_started_at=None,
        last_error=error,
    )


def test_committed_inventory_stays_ready_while_refresh_is_in_flight() -> None:
    state = _state(committed=True, error='previous attempt failed')
    started_at = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    _mark_inventory_collection_started(state, started_at=started_at)

    assert state.status == 'ready'
    assert state.last_started_at == started_at
    assert state.last_error == 'previous attempt failed'


def test_committed_inventory_stays_ready_when_refresh_fails() -> None:
    state = _state(committed=True)

    _mark_inventory_collection_failed(state, RuntimeError('provider timeout'))

    assert state.status == 'ready'
    assert state.last_error == 'provider timeout'


def test_initial_inventory_collection_has_no_ready_snapshot_until_commit() -> None:
    state = _state(committed=False)
    started_at = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    _mark_inventory_collection_started(state, started_at=started_at)
    assert state.status == 'collecting'

    _mark_inventory_collection_failed(state, RuntimeError('provider unavailable'))
    assert state.status == 'failed'
    assert state.last_error == 'provider unavailable'


def test_dashboard_kpis_require_committed_inventory_before_zero_is_observable() -> None:
    active = SimpleNamespace(id=11)
    historical = SimpleNamespace(integration_instance_id=99, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    pending = SimpleNamespace(integration_instance_id=11, last_committed_at=None)

    assert _overview_inventory_kpi_evidence([active], []) == ([], 'Not Collected')
    assert _overview_inventory_kpi_evidence([active], [pending, historical]) == ([], 'Not Collected')

    committed = SimpleNamespace(integration_instance_id=11, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    assert _overview_inventory_kpi_evidence([active], [committed]) == ([11], 'Committed Inventory')


def test_dashboard_fleet_kpi_evidence_excludes_inactive_and_discloses_partial_coverage() -> None:
    active_providers = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
    committed = SimpleNamespace(integration_instance_id=11, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    pending = SimpleNamespace(integration_instance_id=12, last_committed_at=None)
    retired = SimpleNamespace(integration_instance_id=99, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))

    assert _overview_inventory_kpi_evidence(active_providers, [committed, pending, retired]) == (
        [11],
        'Partial Inventory (1/2)',
    )
    complete = SimpleNamespace(integration_instance_id=12, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    assert _overview_inventory_kpi_evidence(active_providers, [committed, complete, retired]) == (
        [11, 12],
        'Committed Inventory',
    )
    assert _overview_inventory_kpi_evidence([], [retired]) == ([], 'Not Collected')


def test_registry_operations_inventory_snapshot_never_uses_unbound_committed_count() -> None:
    """Reproduce the previous /overview section 500 from the inventory-item projection."""
    counts = {'projects': 2, 'repositories': 3, 'artifacts': 5, 'tags': 8}

    pending = _overview_inventory_items(
        counts,
        artifact_total=5,
        total_size_bytes=4096,
        public_project_count=1,
        has_committed_inventory=False,
    )
    assert len(pending) == 6
    assert {item['value'] for item in pending} == {'Not Collected'}

    observed = _overview_inventory_items(
        counts,
        artifact_total=5,
        total_size_bytes=4096,
        public_project_count=1,
        has_committed_inventory=True,
    )
    assert {item['label']: item['value'] for item in observed} == {
        'Projects': 2,
        'Repositories': 3,
        'Artifacts': 5,
        'Tags': 8,
        'Artifact Footprint': '4.00 KiB',
        'Public Projects': 1,
    }


def test_registry_operations_committed_empty_snapshot_is_numeric_zero() -> None:
    observed = _overview_inventory_items(
        {'projects': 0, 'repositories': 0, 'artifacts': 0, 'tags': 0},
        artifact_total=0,
        total_size_bytes=0,
        public_project_count=0,
        has_committed_inventory=True,
    )
    assert [item['value'] for item in observed] == [0, 0, 0, 0, '0 B', 0]


def test_registry_signal_updated_age_uses_relative_committed_time() -> None:
    committed_at = datetime.now(UTC) - timedelta(minutes=28, seconds=30)

    assert _human_time(committed_at) == '28m ago'
    assert _human_time(None) == 'Not Collected'


def test_registry_data_freshness_metrics_source_counts_validated_binding_coverage() -> None:
    context = {
        'latest_committed_at': None,
        'stale_snapshot_count': 0,
        'failed_refresh_count': 0,
    }
    stats = {
        'committed_count': 0,
        'metrics_ready_count': 2,
        'analytics_ready_count': 0,
        'artifact_total': 0,
        'scanned_count': 0,
        'latest_security_at': None,
        'latest_analytics_at': None,
    }
    partial = _fleet_freshness(context=context, provider_count=3, stats=stats)
    assert [item['label'] for item in partial] == [
        'Inventory Snapshot', 'Metrics Source', 'Security Snapshot', 'Analytics Snapshot'
    ]
    assert (partial[1]['status'], partial[1]['tone'], partial[1]['value']) == (
        'Partial', 'warning', '2 / 3 providers'
    )
    assert 'not committed metrics snapshots' in partial[1]['description']

    stats['metrics_ready_count'] = 3
    ready = _fleet_freshness(context=context, provider_count=3, stats=stats)[1]
    assert (ready['status'], ready['value']) == ('Ready', '3 / 3 providers')

    stats['metrics_ready_count'] = 0
    missing = _fleet_freshness(context=context, provider_count=3, stats=stats)[1]
    assert (missing['status'], missing['value']) == ('Not Bound', '0 / 3 providers')


def test_registry_selected_metrics_freshness_describes_bound_source_not_snapshot() -> None:
    metrics = {17: {'status': 'ready', 'label': 'Ready', 'tone': 'normal', 'selected_source': 'Prometheus'}}
    rows = _selected_provider_freshness(
        selected_provider=SimpleNamespace(id=17),
        state_by_provider={},
        metrics_by_provider=metrics,
        analytics_by_provider={},
        artifact_total=0,
        scanned_count=0,
        latest_security_at=None,
    )
    assert len(rows) == 4
    assert rows[1]['label'] == 'Metrics Source'
    assert rows[1]['value'] == 'Prometheus'
    assert rows[1]['status'] == 'Ready'
    assert 'not a committed metrics snapshot' in rows[1]['description']


def test_registry_capacity_usage_and_quota_horizon_rank_from_full_committed_scope() -> None:
    projects = [
        {
            'project_name': f'project-{i}',
            'provider_name': 'Harbor',
            'usage_bytes': float(700 - i * 100),
            'quota_bytes': 1000.0,
            'utilization_percent': float(70 - i * 10),
            'days_to_quota': 2.0 if i == 6 else (15.0 if i == 5 else None),
        }
        for i in range(7)
    ]
    usage = _registry_top_consumers(projects)
    quota = _registry_quota_watch(projects)
    insights = _registry_consumer_insights(projects)

    assert len(usage) == 5
    assert [item['project_name'] for item in usage[:3]] == ['project-0', 'project-1', 'project-2']
    assert [item['project_name'] for item in quota] == ['project-6', 'project-5']
    assert quota[0]['days_to_quota_display'] == '2.0 days'
    assert quota[0]['usage_display'] == '100 B'
    assert insights == {'project_count': 7, 'horizon_count': 2, 'high_utilization_count': 0}


def test_registry_consumer_rankings_preserve_zero_and_missing_evidence() -> None:
    no_usage = {
        'project_name': 'no-usage',
        'provider_name': 'Harbor',
        'usage_bytes': None,
        'quota_bytes': 100.0,
        'utilization_percent': None,
        'days_to_quota': 0.0,
    }
    observed_zero = {
        'project_name': 'observed-zero',
        'provider_name': 'Harbor',
        'usage_bytes': 0.0,
        'quota_bytes': 100.0,
        'utilization_percent': 0.0,
        'days_to_quota': None,
    }
    projects = [no_usage, observed_zero]
    usage = _registry_top_consumers(projects)
    quota = _registry_quota_watch(projects)

    assert [item['project_name'] for item in usage] == ['observed-zero']
    assert usage[0]['usage_display'] == '0 B'
    assert usage[0]['utilization_display'] == '0.0%'
    assert [item['project_name'] for item in quota] == ['no-usage']
    assert quota[0]['usage_display'] == 'N/A'
    assert quota[0]['utilization_display'] == 'N/A'
    assert quota[0]['days_to_quota_display'] == '0.0 days'
    assert _registry_consumer_insights(projects) == {
        'project_count': 2,
        'horizon_count': 1,
        'high_utilization_count': 0,
    }
    assert _registry_quota_watch([observed_zero]) == []


def test_registry_consumers_high_utilization_is_evidence_qualified() -> None:
    projects = [
        {
            'project_name': name,
            'provider_name': 'Harbor',
            'usage_bytes': 90.0,
            'quota_bytes': 100.0,
            'utilization_percent': percent,
            'days_to_quota': None,
        }
        for name, percent in [('high', 90.0), ('unknown', None), ('low', 89.9)]
    ]
    assert _registry_consumer_insights(projects) == {
        'project_count': 3,
        'horizon_count': 0,
        'high_utilization_count': 1,
    }


def test_registry_capacity_cards_distinguish_used_free_and_inventory_evidence() -> None:
    posture = {
        'total_usage': 53 * 1024 * 1024,
        'total_quota': 11 * 1024 * 1024 * 1024,
        'quota_utilization': 0.5,
        'quota_headroom': (11 * 1024 * 1024 * 1024) - (53 * 1024 * 1024),
        'risk': 'Low',
        'insight': 'Within quota.',
        'risk_detail': 'Headroom remains.',
        'recommended_action': 'Review growth.',
    }
    result = _registry_capacity_summary(
        scoped_providers=[SimpleNamespace(id=1)],
        committed_snapshot_count=1,
        total_size_bytes=53 * 1024 * 1024,
        artifact_total=2,
        analytics_count=1,
        posture=posture,
    )
    footprint, used, free = result['metrics']

    assert [item['progress_label'] for item in result['metrics']] == ['Inventory', 'Used', 'Free']
    assert footprint['progress_percent'] is None
    assert footprint['description'] == '2 committed artifact identities.'
    assert used['progress_percent'] == 0.5
    assert used['value'] == '0.5%'
    assert used['description'] == '53.00 MiB / 11.00 GiB quota.'
    assert free['progress_percent'] == 99.5
    assert free['value'] != 'N/A'


def test_registry_capacity_missing_quota_never_fakes_zero_or_full_progress() -> None:
    posture = {
        'total_usage': 0.0,
        'total_quota': 0.0,
        'quota_utilization': None,
        'quota_headroom': None,
        'risk': 'Unknown',
        'insight': 'Unknown.',
        'risk_detail': 'No quota denominator.',
        'recommended_action': 'Refresh analytics.',
    }
    result = _registry_capacity_summary(
        scoped_providers=[SimpleNamespace(id=1)],
        committed_snapshot_count=1,
        total_size_bytes=0,
        artifact_total=0,
        analytics_count=0,
        posture=posture,
    )
    footprint, used, free = result['metrics']
    assert result['available']
    assert footprint['value'] == '0 B'
    assert footprint['progress_percent'] is None
    assert used['value'] == 'N/A'
    assert used['progress_percent'] is None
    assert free['value'] == 'N/A'
    assert free['progress_percent'] is None
