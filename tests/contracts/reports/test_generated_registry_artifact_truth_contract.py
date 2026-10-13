from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_is_metadata_first_and_does_not_claim_existence() -> None:
    src = (ROOT / 'app/reports/generated/service.py').read_text()
    page = (ROOT / 'app/templates/reports/generated/index.html').read_text()
    assert "'exists': False," in src
    assert "artifact_access.get('verified') is False" in src
    assert "'label': 'Artifact Referenced' if report.status == 'ready' else 'Archived Reference'" in src
    assert 'get_report_storage_backend_status(backend_name)' in src
    assert 'verify_artifact=False' in src
    assert "artifact_access.get('state') == 'referenced'" in src
    assert "report.artifact_access.state == 'referenced'" in page
    assert 'Reference Not Verified' in page


def test_detail_keeps_exact_per_artifact_probe_and_authoritative_download() -> None:
    src = (ROOT / 'app/reports/generated/service.py').read_text()
    assert '_probe_report_file(report.file_path)' in src
    assert "if bool(artifact_access.get('verified', verify_artifact))" in src
    assert "report.status == 'archived' and bool(artifact_access['reachable']) and file_exists" in src
