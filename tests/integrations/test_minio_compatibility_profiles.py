import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'app/integrations/storage/object_storage/providers/minio/compatibility.py'
SPEC = spec_from_file_location('kaori_minio_compatibility_test_target', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
compatibility = module_from_spec(SPEC)
sys.modules[SPEC.name] = compatibility
SPEC.loader.exec_module(compatibility)


def test_minio_qualified_release_resolves_profile_and_supported_range() -> None:
    result = compatibility.evaluate_minio_release(compatibility.SUPPORTED_RELEASE, product='minio')

    assert result.readiness == 'ready'
    assert result.profile_key == compatibility.PROFILE_KEY
    assert compatibility.SUPPORTED_RELEASE in result.supported_range


def test_astor_does_not_inherit_minio_compatibility_range() -> None:
    policy = compatibility.compatibility_policy_view('astor', '2024.08')
    result = compatibility.evaluate_minio_release('2024.08', product='astor')

    assert policy['profile_label'] == 'Qualification Required'
    assert 'Product-Specific' in policy['supported_range']
    assert result.readiness == 'blocked'
    assert result.status == 'product_unqualified'
    assert result.profile_key is None
