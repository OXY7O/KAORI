from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_security_evidence_is_digest_oriented() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    assert 'class RegistryScanSnapshot' in models
    assert 'class RegistryVulnerability' in models
    assert "UniqueConstraint('repository_id', 'digest'" in models
    assert 'get_vulnerability_report' in sync
    assert 'vulnerability_summary' in sync
    assert 'RegistryVulnerability(' in sync


def test_security_page_uses_committed_evidence_only() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    assert 'build_security' in presentation
    assert 'RegistryArtifact.query' in presentation
    assert 'HarborClient' not in presentation

def test_registry_scan_evidence_semantics_are_shared_by_dashboard_and_intelligence() -> None:
    contracts = (ROOT / 'app/artifact_registry/security/contracts.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    evaluator = (ROOT / 'app/intelligence/registry_recommendations.py').read_text()

    assert "SUCCESSFUL_REGISTRY_SCAN_STATUSES = frozenset({'success', 'finished', 'completed'})" in contracts
    assert 'def registry_scan_evidence_ready(value: str | None) -> bool:' in contracts
    assert 'SUCCESSFUL_REGISTRY_SCAN_STATUSES' in presentation
    assert 'registry_scan_evidence_ready(artifact.scan_status)' in presentation
    assert 'registry_scan_evidence_ready(artifact.scan_status)' in evaluator
    assert "if not registry_scan_evidence_ready(artifact.scan_status):" in evaluator
    assert "if not str(artifact.scan_status or '').strip():" not in evaluator

