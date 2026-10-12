from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.artifact_registry.security.presentation import _snapshot_status


def test_recent_global_job_does_not_make_old_committed_scan_current() -> None:
    old = datetime.now(UTC) - timedelta(days=3)
    result = _snapshot_status(
        artifact_total=2, evidence_count=2, latest_job=None,
        latest_success=None, latest_evidence_at=old,
    )
    assert result['status'] == 'Stale'
    assert result['latest_collected_at'] == old


def test_missing_evidence_timestamp_never_claims_ready_with_metadata_only() -> None:
    result = _snapshot_status(
        artifact_total=2, evidence_count=2, latest_job=None,
        latest_success=None, latest_evidence_at=None,
    )
    assert result['status'] == 'Age Unverified'
    assert result['tone'] == 'warning'


def test_partial_current_coverage_never_claims_ready() -> None:
    result = _snapshot_status(
        artifact_total=2, evidence_count=1, latest_job=None,
        latest_success=None, latest_evidence_at=datetime.now(UTC),
    )
    assert result['status'] == 'Partial'


def test_report_and_artifact_scope_use_actual_committed_snapshot_timestamps() -> None:
    source = (
        Path(__file__).resolve().parents[3] /
        'app/artifact_registry/security/presentation.py'
    ).read_text(encoding='utf-8')
    assert 'current_scanned_artifacts = successful_scan_scope.filter(' in source
    assert 'RegistryScanSnapshot.observed_at >= datetime.now(UTC)' in source
    assert 'latest_evidence_at = successful_scan_scope.with_entities(' in source
    assert 'artifact_freshness = _freshness(security_at)' in source
    assert "latest_success.completed_at" not in source
    assert "'snapshot_label': artifact_freshness['label']" in source
