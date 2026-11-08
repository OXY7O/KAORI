from werkzeug.datastructures import MultiDict

from app.reports.report_templates.service import get_custom_template_filtered_query, get_selected_filters


def test_template_sql_filter_contains_domain_family_and_format() -> None:
    query = get_custom_template_filtered_query(
        get_selected_filters(MultiDict([('domain', 'kubernetes'), ('family', 'analytics'), ('output_format', 'pdf')]))
    )
    sql = str(query)
    assert 'report_templates.report_domain' in sql
    assert 'report_templates.report_type IN' in sql
    assert 'lower(report_templates.output_format)' in sql


def test_template_search_is_a_database_predicate() -> None:
    query = get_custom_template_filtered_query(get_selected_filters(MultiDict([('search', 'Harbor')])))
    sql = str(query)
    assert 'LIKE' in sql
    assert 'report_templates.name' in sql
