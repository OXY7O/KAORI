from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYTICS = (ROOT / 'app/artifact_registry/analytics.py').read_text()


def test_registry_analytics_worker_streams_artifact_scalars_not_orm_estate():
    worker = ANALYTICS.split('def _registry_bounded_state(', 1)[1].split(
        'def _growth_payload(', 1
    )[0]
    assert 'yield_per(250)' in worker
    assert 'RegistryArtifact.id.in_(select(runtime_ids.c.artifact_id))' in worker
    assert '.with_entities(' in worker
    assert '_registry_committed_state(' not in ANALYTICS
    assert 'projects = RegistryProject.query.filter_by(integration_instance_id=identity_id).all()' not in ANALYTICS


def test_security_findings_require_usable_scan_status():
    worker = ANALYTICS.split('def _registry_bounded_state(', 1)[1].split(
        'def _growth_payload(', 1
    )[0]
    assert 'scan_ready = bool(registry_scan_evidence_ready(scan))' in worker
    assert "summary = findings if isinstance(findings, dict) and scan_ready else {}" in worker


def test_governance_unconfigured_is_independent_from_absent_assessment():
    worker = ANALYTICS.split('def _registry_bounded_state(', 1)[1].split(
        'def _growth_payload(', 1
    )[0]
    assert "RegistryProjectGovernance.retention_status == 'not_configured'" in worker
    assert "RegistryProjectGovernance.immutability_status == 'not_configured'" in worker
    assert "RegistryProjectGovernance.retention_status == 'configured'" in worker


def test_analytics_generation_authority_is_committed_and_checked_again():
    assert "'inventory_committed_at': (" in ANALYTICS
    assert "'governance_committed_at': (" in ANALYTICS
    assert 'db.session.refresh(inventory_state)' in ANALYTICS
    assert "if current_generation != domain['evidence']['inventory_committed_at']:" in ANALYTICS
    assert 'Registry inventory generation changed during Analytics materialization.' in ANALYTICS


def test_committed_kubernetes_generation_is_an_analytics_freshness_dependency():
    common = (ROOT / 'app/artifact_registry/presentation_common.py').read_text()
    assert "'correlation_input_signature': runtime_input_signature(db.session)" in ANALYTICS
    assert "runtime_input_signature(db.session) != domain['evidence']['correlation_input_signature']" in ANALYTICS
    assert "runtime_input_signature(db.session) != evidence.get('correlation_input_signature')" in common
    assert 'security_latest_scan_at' in ANALYTICS
    assert 'security_latest_scan_at' in common
    assert 'runtime_observed_at' in common
