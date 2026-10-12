from pathlib import Path


def test_verification_uses_unique_object_keys_and_confirms_cleanup():
    s = (Path(__file__).resolve().parents[3] / 'app/reports/storage/service.py').read_text()
    block = s[s.index('def verify_active_report_storage()'):s.index('def scan_report_storage_integrity(')]
    assert 'uuid4().hex' in block
    assert 'cleanup_confirmed = not bool(backend.exists(stored_file.object_key))' in block
    assert 'verified = exists and cleanup_confirmed' in block
    assert "backend.delete(stored_file.object_key)" in block
    assert "'cleanup_confirmed': cleanup_confirmed" in block
    assert 'if stored_file is not None and not cleanup_confirmed' in block
    assert 'temp_path.unlink(missing_ok=True)' in block
