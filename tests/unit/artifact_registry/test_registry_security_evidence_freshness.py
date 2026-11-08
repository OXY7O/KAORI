from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.artifact_registry.security.presentation import _snapshot_status


def test_recent_global_job_does_not_make_old_committed_scan_current() -> None:
    old = datetime.now(UTC) - timedelta(days=3)
    result = _snapshot_status(
        artifact_total=2,
        evidence_count=2,
        latest_job=None,
        latest_success=None,
        latest_evidence_at=old,
    )
    assert result['status'] == 'Stale'
    assert result['latest_collected_at'] == old


def test_missing_evidence_timestamp_never_claims_ready_with_metadata_only() -> None:
    result = _snapshot_status(
        artifact_total=2,
        evidence_count=2,
        latest_job=None,
        latest_success=None,
        latest_evidence_at=None,
    )
    assert result['status'] == 'Age Unverified'
    assert result['tone'] == 'warning'


def test_partial_current_coverage_never_claims_ready() -> None:
    result = _snapshot_status(
        artifact_total=2,
        evidence_count=1,
        latest_job=None,
        latest_success=None,
        latest_evidence_at=datetime.now(UTC),
    )
    assert result['status'] == 'Partial'


def test_report_and_artifact_scope_use_actual_committed_snapshot_timestamps() -> None:
    source = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/security/presentation.py').read_text(
        encoding='utf-8'
    )
    assert 'current_scanned_artifacts = (' in source
    assert 'successful_scan_scope.filter(' in source
    assert 'RegistryScanSnapshot.observed_at >= datetime.now(UTC)' in source
    assert 'latest_evidence_at = successful_scan_scope.with_entities(' in source
    assert 'artifact_freshness = _freshness(security_at)' in source
    assert 'latest_success.completed_at' not in source
    assert "'snapshot_label': artifact_freshness['label']" in source


def test_observed_empty_inventory_is_not_inventory_required() -> None:
    snapshot = _snapshot_status(
        artifact_total=0,
        evidence_count=0,
        latest_job=None,
        latest_success=None,
        latest_evidence_at=None,
        inventory_committed=True,
    )
    assert snapshot['status'] == 'No Artifacts'
    assert snapshot['tone'] == 'info'


def test_unobserved_inventory_still_requires_collection() -> None:
    snapshot = _snapshot_status(
        artifact_total=0,
        evidence_count=0,
        latest_job=None,
        latest_success=None,
        latest_evidence_at=None,
        inventory_committed=False,
    )
    assert snapshot['status'] == 'Inventory Required'


def test_last_success_not_limited_to_last_50_attempts() -> None:
    adapter = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/security/job_adapter.py').read_text()
    assert 'jobs.filter(JobExecution.status.in_(_SUCCESS_STATUSES))' in adapter
    assert 'latest_success = next(' not in adapter
