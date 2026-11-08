from app.reports.generate.service import MAX_REPORT_NAME_LENGTH, validate_report_name


def test_report_name_accepts_max_length_and_auto_generated_blank() -> None:
    assert MAX_REPORT_NAME_LENGTH == 255
    assert validate_report_name('x' * MAX_REPORT_NAME_LENGTH) == []
    assert validate_report_name('  ') == []


def test_report_name_rejects_over_limit_without_truncation() -> None:
    assert validate_report_name('x' * 256) == ['Report name must be 255 characters or fewer.']


def test_report_name_counts_unicode_codepoints_not_bytes() -> None:
    assert validate_report_name('名' * 255) == []
    assert validate_report_name('名' * 256) == ['Report name must be 255 characters or fewer.']


def test_invalid_name_is_rejected_before_database_scope_reads(monkeypatch) -> None:
    from app.reports.catalog import REPORT_TYPE_OPTIONS
    from app.reports.generate.service import build_default_form_state, validate_form_state

    def forbidden(*_args, **_kwargs):
        raise AssertionError('invalid name must not reach database scope reads')

    monkeypatch.setattr('app.reports.generate.service._validate_primary_scope', forbidden)
    state = build_default_form_state(report_type=REPORT_TYPE_OPTIONS[0]['value'])
    state['name'] = 'x' * 256
    assert validate_form_state(state) == ['Report name must be 255 characters or fewer.']
