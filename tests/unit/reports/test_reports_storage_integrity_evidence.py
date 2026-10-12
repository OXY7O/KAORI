from app.reports.storage.service import build_storage_integrity_presentation


def test_scan_evidence_is_exposed_in_template_schema():
    result = build_storage_integrity_presentation({'checked_count': 2, 'total_reference_count': 3, 'available_count': 2, 'missing_count': 0, 'error_count': 0})
    assert (result['checked'], result['available'], result['missing'], result['errors']) == (2, 2, 0, 0)
    assert result['status'] == 'Partial Coverage'
    assert result['is_limited']
    assert result['tone'] == 'warning'


def test_zero_and_missing_reference_states_are_not_green():
    empty = build_storage_integrity_presentation({'checked_count': 0, 'total_reference_count': 0})
    assert empty['status'] == 'No References' and empty['tone'] == 'unknown'
    missing = build_storage_integrity_presentation({'checked_count': 1, 'total_reference_count': 1, 'missing_count': 1})
    assert missing['status'] == 'Missing Artifacts' and missing['tone'] == 'critical'
