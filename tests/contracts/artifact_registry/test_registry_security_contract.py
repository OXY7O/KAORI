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
