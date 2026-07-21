import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/integrations/binding_posture.py'
SPEC = importlib.util.spec_from_file_location('binding_posture_contract', MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
resolve_binding_operational_posture = MODULE.resolve_binding_operational_posture


def test_ready_requires_source_and_binding_ready():
    posture = resolve_binding_operational_posture(
        source_readiness='ready',
        binding_validation='ready',
    )
    assert posture['status'] == 'ready'


def test_binding_validation_is_independent_from_source_readiness():
    posture = resolve_binding_operational_posture(
        source_readiness='ready',
        binding_validation='validation_required',
    )
    assert posture['status'] == 'validation_required'
    assert posture['label'] == 'Binding Validation Required'


def test_source_readiness_can_block_a_valid_binding():
    posture = resolve_binding_operational_posture(
        source_readiness='blocked',
        binding_validation='ready',
    )
    assert posture['status'] == 'blocked'
    assert posture['label'] == 'Source Blocked'
