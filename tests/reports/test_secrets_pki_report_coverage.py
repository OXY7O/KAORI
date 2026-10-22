"""Secrets & PKI reporting candidates must never become executable by catalog accident."""

import pytest

from app.reports.catalog import (
    REPORT_COVERAGE_DOMAINS,
    REPORT_TYPE_SPECS,
    ReportContractError,
    get_report_type_spec,
)
from app.reports.overview.service import get_report_type_coverage


def test_secrets_pki_coverage_is_planned_with_no_published_report_types():
    spec = next(item for item in REPORT_COVERAGE_DOMAINS if item.key == 'secrets_pki')
    assert spec.status == 'Planned'
    assert spec.tone == 'info'
    assert len(spec.items) == 6
    assert len({item.name for item in spec.items}) == 6
    assert not any(item.domain == 'secrets_pki' for item in REPORT_TYPE_SPECS)


def test_reports_overview_includes_candidates_only_not_executable():
    coverage = get_report_type_coverage()
    groups = [item for item in coverage['domains'] if item['key'] == 'secrets_pki']
    assert len(groups) == 1
    group = groups[0]
    assert group['status'] == 'Planned'
    assert group['published_count'] == group['available_count'] == 0
    assert group['candidate_count'] == 6
    assert len(group['items']) == 6
    assert all(item['status'] == 'Planned' for item in group['items'])
    assert all('path' not in item and 'value' not in item for item in group['items'])


def test_nonexistent_secrets_pki_report_type_is_rejected():
    with pytest.raises(ReportContractError):
        get_report_type_spec('secrets_pki_inventory')
