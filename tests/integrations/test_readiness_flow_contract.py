import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/integrations/readiness.py'
spec = importlib.util.spec_from_file_location('kaori_readiness_contract', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
resolve_binding_operational_status = module.resolve_binding_operational_status
resolve_cluster_coverage = module.resolve_cluster_coverage


class Source:
    readiness_status = 'ready'
    enabled = True


class Binding:
    validation_status = 'ready'
    enabled = True


def test_binding_requires_source_and_binding_readiness():
    assert resolve_binding_operational_status(
        source_readiness='ready', binding_validation='ready'
    ) == {'status': 'ready', 'label': 'Ready'}
    assert resolve_binding_operational_status(
        source_readiness='validation_required', binding_validation='ready'
    )['label'] == 'Source Validation Required'
    assert resolve_binding_operational_status(
        source_readiness='ready', binding_validation='validation_required'
    )['label'] == 'Binding Validation Required'


def test_cluster_downstream_coverage_waits_for_kubernetes_api():
    result = resolve_cluster_coverage(
        kubernetes_readiness='validation_required', source=Source(), binding=Binding()
    )
    assert result == {'status': 'validation_required', 'label': 'Waiting For Kubernetes'}


def test_cluster_downstream_coverage_becomes_ready_after_all_gates():
    result = resolve_cluster_coverage(
        kubernetes_readiness='ready', source=Source(), binding=Binding()
    )
    assert result == {'status': 'ready', 'label': 'Ready'}
