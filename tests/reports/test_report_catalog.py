from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.reports.catalog import (
    ANALYTICS_REPORT_TYPES,
    FORMAT_CSV,
    FORMAT_PDF,
    FORMAT_XLSX,
    INVENTORY_REPORT_TYPES,
    OUTPUT_FORMAT_SPECS,
    REPORT_TYPE_SPECS,
    REQUIRES_SELECTED_CLUSTER_REPORT_TYPES,
    ReportContractError,
    get_allowed_output_formats,
    get_default_output_format,
    validate_report_contract,
    validate_report_instance,
)


def test_report_family_format_matrix_is_exact() -> None:
    assert ANALYTICS_REPORT_TYPES
    assert INVENTORY_REPORT_TYPES
    assert ANALYTICS_REPORT_TYPES.isdisjoint(INVENTORY_REPORT_TYPES)

    for report_type in ANALYTICS_REPORT_TYPES:
        assert get_allowed_output_formats(report_type) == (FORMAT_PDF, FORMAT_CSV)
        assert get_default_output_format(report_type) == FORMAT_PDF

    for report_type in INVENTORY_REPORT_TYPES:
        assert get_allowed_output_formats(report_type) == (FORMAT_XLSX, FORMAT_CSV)
        assert get_default_output_format(report_type) == FORMAT_XLSX


def test_every_report_type_requires_one_selected_cluster() -> None:
    all_report_types = {spec.value for spec in REPORT_TYPE_SPECS}
    assert REQUIRES_SELECTED_CLUSTER_REPORT_TYPES == all_report_types

    for spec in REPORT_TYPE_SPECS:
        with pytest.raises(ReportContractError, match='selected Kubernetes cluster'):
            validate_report_contract(
                report_type=spec.value,
                output_format=spec.default_format,
                cluster_id=None,
            )


def test_unsupported_family_format_combinations_are_rejected() -> None:
    with pytest.raises(ReportContractError, match='supports only PDF, CSV'):
        validate_report_contract(
            report_type='analytics_overview',
            output_format=FORMAT_XLSX,
            cluster_id='cluster-1',
        )

    with pytest.raises(ReportContractError, match='supports only XLSX, CSV'):
        validate_report_contract(
            report_type='node_inventory',
            output_format=FORMAT_PDF,
            cluster_id='cluster-1',
        )


def test_report_instance_validation_uses_the_same_contract() -> None:
    report = SimpleNamespace(
        report_type='service_inventory',
        output_format=FORMAT_CSV,
        cluster_id='cluster-1',
    )
    validate_report_instance(report)

    report.cluster_id = ''
    with pytest.raises(ReportContractError):
        validate_report_instance(report)


def test_output_format_metadata_is_complete_and_unique() -> None:
    assert set(OUTPUT_FORMAT_SPECS) == {FORMAT_PDF, FORMAT_XLSX, FORMAT_CSV}
    assert {spec.extension for spec in OUTPUT_FORMAT_SPECS.values()} == {'.pdf', '.xlsx', '.csv'}
    assert OUTPUT_FORMAT_SPECS[FORMAT_CSV].mimetype == 'text/csv'
