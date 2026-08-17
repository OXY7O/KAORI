from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/messages.py'
SPEC = spec_from_file_location('kaori_kubernetes_messages_test_module', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
compact_readiness_reason = MODULE.compact_readiness_reason


def test_compact_readiness_reason_rewrites_persisted_legacy_lifecycle_copy() -> None:
    legacy = (
        'Kubernetes v1.29.5 is in the KAORI legacy lifecycle band. '
        'Stable APIs remain usable, but upgrade planning is required before readiness can return to Ready.'
    )

    assert compact_readiness_reason(legacy) == ('Kubernetes v1.29.5 is in a legacy lifecycle band. Plan an upgrade.')


def test_compact_readiness_reason_preserves_unrelated_findings() -> None:
    finding = 'Kubernetes API request timed out.'

    assert compact_readiness_reason(finding) == finding
