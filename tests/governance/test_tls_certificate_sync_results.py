from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/kubernetes/governance/tls_certificates/results.py'
SPEC = spec_from_file_location('tls_certificate_sync_results', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
classify_tls_sync_outcome = MODULE.classify_tls_sync_outcome


def test_tls_sync_outcome_succeeds_without_failures() -> None:
    assert classify_tls_sync_outcome(target_count=3, failed_count=0) == 'succeeded'


def test_tls_sync_outcome_is_partial_when_some_clusters_fail() -> None:
    assert classify_tls_sync_outcome(target_count=3, failed_count=1) == 'partially_succeeded'


def test_tls_sync_outcome_fails_when_every_cluster_fails() -> None:
    assert classify_tls_sync_outcome(target_count=2, failed_count=2) == 'failed'


def test_partial_when_collection_warning_exists_without_fatal_failure():
    assert (
        classify_tls_sync_outcome(
            target_count=3,
            failed_count=0,
            warning_count=1,
        )
        == 'partially_succeeded'
    )
