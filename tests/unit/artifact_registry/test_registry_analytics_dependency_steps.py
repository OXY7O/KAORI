"""Source-independent Registry Analytics dependency readiness contracts (#5123)."""

from app.artifact_registry.analytics_job_adapter import registry_analytics_dependency_steps


def _statuses(*, registered: int, eligible: int, evidence: list[dict]) -> dict[str, dict[str, str]]:
    steps = registry_analytics_dependency_steps(
        registered_count=registered,
        eligible_count=eligible,
        evidence=evidence,
    )
    assert [item['key'] for item in steps] == ['domain', 'metrics', 'alerts']
    return {item['key']: item for item in steps}


def test_missing_worker_snapshot_does_not_claim_metrics_or_alert_binding_missing() -> None:
    steps = _statuses(registered=1, eligible=1, evidence=[])

    assert steps['domain']['status'] == 'Ready'
    assert steps['metrics']['status'] == 'Not Collected'
    assert steps['alerts']['status'] == 'Not Collected'
    assert 'not a live binding' in steps['metrics']['detail']


def test_committed_metrics_remain_ready_without_alert_evidence() -> None:
    steps = _statuses(
        registered=1,
        eligible=1,
        evidence=[{'current': True, 'metrics': {'status': 'ready'}, 'alerts': {'status': 'unavailable'}}],
    )

    assert steps['metrics']['status'] == 'Evidence Ready'
    assert steps['metrics']['tone'] == 'normal'
    assert steps['alerts']['status'] == 'Evidence Unavailable'
    assert steps['alerts']['tone'] == 'unknown'


def test_alertmanager_fallback_is_visible_without_claiming_primary_lifecycle() -> None:
    steps = _statuses(
        registered=1,
        eligible=1,
        evidence=[
            {
                'current': True,
                'metrics': {'status': 'partial'},
                'alerts': {'status': 'ready', 'fallback_used': True},
            }
        ],
    )

    assert steps['metrics']['status'] == 'Partial Evidence'
    assert steps['alerts']['status'] == 'Fallback Evidence'
    assert steps['alerts']['tone'] == 'warning'


def test_stale_and_partially_covered_sources_cannot_report_current_ready() -> None:
    stale = _statuses(
        registered=1,
        eligible=1,
        evidence=[{'current': False, 'metrics': {'status': 'ready'}, 'alerts': {'status': 'ready'}}],
    )
    assert stale['metrics']['status'] == 'Partial Evidence'
    assert stale['alerts']['status'] == 'Partial Evidence'

    fleet = _statuses(
        registered=2,
        eligible=2,
        evidence=[{'current': True, 'metrics': {'status': 'ready'}, 'alerts': {'status': 'ready'}}],
    )
    assert fleet['metrics']['status'] == 'Partial Evidence'
    assert fleet['alerts']['status'] == 'Partial Evidence'


def test_unvalidated_registry_does_not_fabricate_source_readiness() -> None:
    steps = _statuses(registered=1, eligible=0, evidence=[])

    assert steps['domain']['status'] == 'Validation Required'
    assert steps['metrics']['status'] == 'Not Collected'
    assert steps['alerts']['status'] == 'Not Collected'
