from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_paginates_custom_templates_in_sql_not_python() -> None:
    source = (ROOT / 'app/reports/report_templates/service.py').read_text()
    payload = source.split('def get_report_templates_payload(', 1)[1].split('def get_custom_template_aggregate_items(', 1)[0]
    assert 'get_all_template_items()' not in payload
    assert 'get_custom_template_filtered_query(selected_filters)' in payload
    assert '.offset(custom_offset)' in payload
    assert '.limit(remaining)' in payload
    assert 'build_templates_pagination(args, selected_filters, total)' in payload
    assert 'get_custom_template_aggregate_items()' in payload
    assert 'select(func.count()).select_from(custom_statement.order_by(None).subquery())' in payload


def test_kpi_counts_are_weighted_aggregate_not_full_entity_materialization() -> None:
    source = (ROOT / 'app/reports/report_templates/service.py').read_text()
    assert 'group_by(' in source
    assert "int(item.get('_weight', 1))" in source
    assert 'ReportTemplate.report_type.in_(family_types)' in source
    assert 'ReportTemplate.status == filters' in source
