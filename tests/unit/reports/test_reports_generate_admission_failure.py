from werkzeug.datastructures import MultiDict

from app.reports.catalog import REPORT_TYPE_OPTIONS
from app.reports.generate.service import create_report_request


def _contract(family: str) -> str:
    return next(item['value'] for item in REPORT_TYPE_OPTIONS if item['family'] == family)


def _block_persistence(monkeypatch) -> None:
    def no_scope_error(*_args, **_kwargs):
        return [], True

    def no_errors(*_args, **_kwargs):
        return []

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Invalid report must fail before storage readiness or persistence')

    monkeypatch.setattr('app.reports.generate.service._validate_primary_scope', no_scope_error)
    monkeypatch.setattr('app.reports.generate.service._validate_namespace_scope', no_errors)
    monkeypatch.setattr('app.reports.generate.service._validate_object_storage_scope_reference', no_errors)
    monkeypatch.setattr('app.reports.generate.service._validate_artifact_registry_scope_reference', no_errors)
    monkeypatch.setattr('app.reports.generate.service.get_report_storage_backend_status', forbidden)


def test_create_rejects_explicit_empty_analytics_sections_without_storage_io(monkeypatch) -> None:
    _block_persistence(monkeypatch)
    accepted, errors, report = create_report_request(
        MultiDict([('report_type', _contract('analytics')), ('period', '30d')]), None
    )
    assert accepted is False and report is None
    assert 'Please select at least one report section.' in errors


def test_create_rejects_unsupported_report_type_without_storage_io(monkeypatch) -> None:
    _block_persistence(monkeypatch)
    accepted, errors, report = create_report_request(MultiDict([('report_type', 'bogus')]), None)
    assert accepted is False and report is None
    assert 'Please select a valid published report type.' in errors


def test_create_rejects_oversized_custom_name_without_storage_io(monkeypatch) -> None:
    _block_persistence(monkeypatch)
    accepted, errors, report = create_report_request(
        MultiDict([('report_type', _contract('analytics')), ('name', '名' * 256)]), None
    )
    assert accepted is False and report is None
    assert 'Report name must be 255 characters or fewer.' in errors
