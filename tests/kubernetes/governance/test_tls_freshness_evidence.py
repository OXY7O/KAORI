from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.kubernetes.governance.tls_certificates.sync_state import (
    _cluster_job_scope,
    _collection_freshness,
    _job_applies_to_cluster,
    _successful_job_evidence_times,
    tls_sync_evidence_is_current,
    tls_sync_stale_after,
)
from app.models.job import JobExecution


def state(secret='collected', ingress='collected', at=None):
    return SimpleNamespace(
        secret_collection_status=secret,
        ingress_mapping_status=ingress,
        collected_at=at,
    )


def test_failed_attempt_cannot_refresh_successful_snapshot_clock():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    old = now - timedelta(days=2)
    # A failure can update state.updated_at but cannot establish freshness.
    failed = state(secret='collection_failed', ingress='collected', at=now)
    failed.updated_at = now
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'],
        states={'a': failed},
        record_times={'a': old},
        stale_after=timedelta(hours=7),
        now=now,
    )
    assert at == old
    assert stale is True
    assert exceptions is True


def test_zero_certificates_can_have_successful_collection_evidence():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'],
        states={'a': state(at=now)},
        record_times={},
        stale_after=timedelta(hours=7),
        now=now,
    )
    assert at == now and stale is False and exceptions is False


def test_fleet_requires_all_clusters_and_all_source_families():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    earlier = now - timedelta(hours=15)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a', 'b', 'c'],
        states={
            'a': state(at=now),
            'b': state(ingress='permission_unavailable', at=earlier),
        },
        record_times={'b': earlier},
        stale_after=timedelta(hours=7),
        now=now,
    )
    assert at == now
    assert stale is True
    assert exceptions is True


def test_recent_secret_evidence_does_not_make_failed_ingress_mapping_complete():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'],
        states={'a': state(ingress='api_unavailable', at=now)},
        record_times={},
        stale_after=timedelta(hours=7),
        now=now,
    )
    assert at == now and stale is False and exceptions is True


def test_last_successful_empty_inventory_requires_target_specific_job_evidence():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    old = now - timedelta(days=2)
    fleet_job = SimpleNamespace(
        status='partially_succeeded',
        completed_at=old,
        payload_json={
            'targets': [
                {'cluster_id': 'empty-but-successful'},
                {'cluster_id': 'failed'},
            ]
        },
        result_summary_json={
            'failures': [{'cluster_id': 'failed', 'error': 'Secret API unavailable'}],
        },
    )
    job_times = _successful_job_evidence_times(
        [fleet_job],
        ['empty-but-successful', 'failed'],
    )
    assert job_times == {'empty-but-successful': old}

    for cluster_id in ('empty-but-successful', 'failed'):
        at, stale, exceptions = _collection_freshness(
            cluster_ids=[cluster_id],
            states={cluster_id: state(secret='collection_failed', at=now)},
            record_times={},
            job_success_times=job_times,
            stale_after=timedelta(hours=7),
            now=now,
        )
        if cluster_id == 'empty-but-successful':
            assert at == old
        else:
            assert at is None
        assert stale is True
        assert exceptions is True


def test_tls_rotation_evidence_window_rejects_missing_future_and_stale_timestamps():
    now = datetime(2026, 10, 23, tzinfo=UTC)
    window = tls_sync_stale_after(360)
    assert window == timedelta(minutes=450)
    assert tls_sync_evidence_is_current(now - window, stale_after=window, now=now)
    assert tls_sync_evidence_is_current(now - timedelta(minutes=1), stale_after=window, now=now)
    assert not tls_sync_evidence_is_current(None, stale_after=window, now=now)
    assert not tls_sync_evidence_is_current(now + timedelta(seconds=1), stale_after=window, now=now)
    assert not tls_sync_evidence_is_current(now - window - timedelta(seconds=1), stale_after=window, now=now)


def test_selected_tls_job_history_filters_canonical_targets_in_sql_before_limit():
    statement = (
        select(JobExecution.id)
        .where(_cluster_job_scope('cluster-a'))
        .order_by(JobExecution.created_at.desc())
        .limit(100)
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    assert 'CAST(job_executions.payload_json AS JSONB) @>' in str(compiled)
    assert 'LIMIT' in str(compiled)
    assert {'targets': [{'cluster_id': 'cluster-a'}]} in compiled.params.values()


def test_fleet_scope_does_not_imply_membership_in_unlisted_cluster():
    job = SimpleNamespace(
        payload_json={
            'scope': 'all_clusters',
            'targets': [{'cluster_id': 'cluster-a'}],
        }
    )
    assert _job_applies_to_cluster(job, 'cluster-a') is True
    assert _job_applies_to_cluster(job, 'cluster-b') is False
    assert _job_applies_to_cluster(job, None) is True


def test_target_specific_old_job_remains_eligible_after_many_other_cluster_jobs():
    now = datetime(2026, 10, 23, tzinfo=UTC)
    old_target = SimpleNamespace(
        status='succeeded',
        completed_at=now - timedelta(days=2),
        payload_json={'targets': [{'cluster_id': 'cluster-a'}]},
        result_summary_json={'failures': []},
    )
    unrelated = [
        SimpleNamespace(
            status='succeeded',
            completed_at=now,
            payload_json={'targets': [{'cluster_id': f'cluster-other-{index}'}]},
            result_summary_json={'failures': []},
        )
        for index in range(150)
    ]
    scoped = [job for job in unrelated + [old_target] if _job_applies_to_cluster(job, 'cluster-a')]
    assert scoped == [old_target]
    assert _successful_job_evidence_times(scoped, ['cluster-a']) == {
        'cluster-a': now - timedelta(days=2)
    }
