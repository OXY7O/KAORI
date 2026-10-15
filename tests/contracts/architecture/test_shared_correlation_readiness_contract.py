"""Guard committed correlation evidence ownership across Registry and Intelligence."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_correlation_readiness_is_shared_committed_kaori_evidence() -> None:
    shared = _read('app/common/registry_runtime_evidence.py')
    producer = _read('app/artifact_registry/correlation.py')

    assert 'def runtime_input_signature(' in shared
    assert 'def runtime_correlation_evidence_readiness(' in shared
    assert 'ClusterInventory.collected_at' in shared
    assert 'RegistryCollectionState.last_committed_at' in shared
    assert "JobExecution.job_type == 'artifact_registry_runtime_correlation'" in shared
    assert '(signature_fn or runtime_input_signature)(session)' in shared
    assert (
        '_committed_runtime_correlation_evidence_readiness(session, signature_fn=runtime_input_signature)' in producer
    )
    assert 'with Session(db.engine) as materialization_session:' in producer


def test_central_intelligence_consumes_shared_evidence_not_registry_implementation() -> None:
    for path in (
        'app/intelligence/service.py',
        'app/intelligence/alert_intelligence/recommendation_source.py',
    ):
        source = _read(path)
        assert 'from app.common.registry_runtime_evidence import runtime_correlation_evidence_readiness' in source
        assert 'from app.artifact_registry.correlation import runtime_correlation_evidence_readiness' not in source
