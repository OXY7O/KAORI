"""Report storage integrity must distinguish malformed URIs from unexpected failures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.reports.storage import service as report_storage


class _Rows:
    def __init__(self, reports: list[SimpleNamespace]) -> None:
        self.reports = reports

    def scalars(self) -> _Rows:
        return self

    def all(self) -> list[SimpleNamespace]:
        return self.reports


class _Session:
    def __init__(self, reports: list[SimpleNamespace]) -> None:
        self.reports = reports

    def scalar(self, _statement: object) -> int:
        return len(self.reports)

    def execute(self, _statement: object) -> _Rows:
        return _Rows(self.reports)


def _mock_report_query(monkeypatch: pytest.MonkeyPatch, uri: str) -> None:
    reports = [SimpleNamespace(id=9, name='Report fixture', file_path=uri)]
    monkeypatch.setattr(report_storage, 'db', SimpleNamespace(session=_Session(reports)))


def test_invalid_storage_uri_is_unknown_and_cannot_be_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_report_query(monkeypatch, 'not-a-storage-uri')

    def missing_artifact(_uri: str) -> bool:
        raise ValueError('Malformed storage URI')

    monkeypatch.setattr(report_storage, 'report_file_exists', missing_artifact)
    result = report_storage.scan_report_storage_integrity()

    assert result['checked_count'] == 1
    assert result['backend_counts'] == {'local': 0, 's3': 0, 'unknown': 1}
    assert result['error_count'] == 1
    assert result['error_samples'][0]['backend'] == 'unknown'
    assert not result['is_healthy']


def test_valid_local_storage_uri_remains_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_report_query(monkeypatch, 'local:reports/valid.pdf')
    monkeypatch.setattr(report_storage, 'report_file_exists', lambda _uri: True)

    result = report_storage.scan_report_storage_integrity()

    assert result['backend_counts'] == {'local': 1, 's3': 0, 'unknown': 0}
    assert result['available_count'] == 1
    assert result['error_count'] == 0
    assert result['is_healthy']


def test_unexpected_uri_parser_defect_is_not_silently_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_report_query(monkeypatch, 'local:reports/valid.pdf')

    def unexpected_parser(_uri: str) -> tuple[str, str]:
        raise RuntimeError('Unexpected report storage parser failure')

    monkeypatch.setattr(report_storage, 'parse_report_storage_uri', unexpected_parser)

    with pytest.raises(RuntimeError, match='Unexpected report storage parser failure'):
        report_storage.scan_report_storage_integrity()
