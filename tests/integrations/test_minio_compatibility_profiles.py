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


def test_minio_qualified_release_maps_to_general_s3_contract() -> None:
    result = compatibility.evaluate_minio_release(compatibility.SUPPORTED_RELEASE_MAX, product='minio')

    assert result.readiness == 'ready'
    assert result.profile_key == 's3-object-storage-v1'
    assert result.qualification_key == 'minio-community-qualified'
    assert compatibility.SUPPORTED_RELEASE_MAX in result.supported_range


def test_newer_minio_release_is_unverified_not_blocked_by_version_alone() -> None:
    result = compatibility.evaluate_minio_release('RELEASE.2026-01-01T00-00-00Z', product='minio')

    assert result.status == 'unverified_version'
    assert result.readiness == 'degraded'
    assert result.profile_key == 's3-object-storage-v1'
    assert result.qualification_key is None


def test_product_without_qualification_uses_general_s3_contract_as_unverified() -> None:
    policy = compatibility.compatibility_policy_view('astor', '2026.01')
    result = compatibility.evaluate_minio_release('2026.01', product='astor')

    assert policy['profile_key'] == 's3-object-storage-v1'
    assert policy['qualification_key'] == 'Unverified Version'
    assert result.readiness == 'degraded'
    assert result.status == 'product_unqualified'
    assert result.profile_key == 's3-object-storage-v1'
