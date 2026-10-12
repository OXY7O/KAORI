from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_archive_reverification_rejects_purged_and_nonverifiable_states() -> None:
    service = read('app/platform_operations/data_lifecycle/retention/service.py')
    block = service.split('def verify_archive_artifact(', 1)[1].split('def get_archive_download_path(', 1)[0]
    assert 'if not artifact.is_verifiable:' in block
    assert 'raise ArchiveVerificationError(' in block


def test_failed_verification_revokes_readiness_and_downloadability() -> None:
    service = read('app/platform_operations/data_lifecycle/retention/service.py')
    model = read('app/models/archive.py')
    block = service.split('def verify_archive_artifact(', 1)[1].split('def get_archive_download_path(', 1)[0]
    assert 'failed_artifact.status = ARCHIVE_STATUS_FAILED' in block
    assert 'failed_artifact.verified_at = None' in block
    assert 'failed_artifact.error_message =' in block
    assert 'ARCHIVE_STATUS_FAILED' not in model.split('def is_downloadable', 1)[1].split('def is_verifiable', 1)[0]


def test_verified_archive_does_not_imply_unfinished_cleanup_completed() -> None:
    service = read('app/platform_operations/data_lifecycle/retention/service.py')
    block = service.split('def verify_archive_artifact(', 1)[1].split('def get_archive_download_path(', 1)[0]
    assert "artifact.operation_mode == 'archive_and_cleanup'" in block
    assert 'artifact.cleanup_deleted_count < artifact.record_count' in block
    assert 'artifact.status = ARCHIVE_STATUS_CLEANUP_PARTIAL' in block
    assert 'no cleanup was retried' in block
    assert 'elif artifact.status == ARCHIVE_STATUS_READY:' in block
