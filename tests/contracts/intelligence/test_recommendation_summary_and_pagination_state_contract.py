import runpy
from pathlib import Path


def test_recommendation_list_uses_presentation_owned_compact_summary():
    service = Path('app/intelligence/service.py').read_text()
    presentation = Path('app/intelligence/finding_presentation.py').read_text()
    records = Path('app/templates/intelligence/partials/_recommendation_records.html').read_text()
    assert 'def compact_recommendation_summary' in presentation
    assert 'def recommendation_table_title' in presentation
    assert 'def recommendation_table_summary' in presentation
    assert "for marker in (' Examples:', ' Example:', ' Examples include:')" in presentation
    assert "item['list_title'] = recommendation_table_title(item, limit=96)" in service
    assert "item['list_summary'] = recommendation_table_summary(item, limit=72)" in service
    assert 'item.list_title|default(item.title, true)' in records
    assert 'item.list_summary|default(item.summary, true)' in records
    assert 'line-clamp-1' in records
    assert 'title="{{ item.summary }}"' in records
    assert "action = _clean(item.get('recommended_action'))" in presentation


def test_pagination_and_filters_have_separate_htmx_ownership():
    filters = Path('app/templates/intelligence/partials/_filters.html').read_text()
    results = Path('app/templates/intelligence/partials/_recommendations_results.html').read_text()
    pagination = Path('app/templates/intelligence/components/_pagination.html').read_text()
    route = Path('app/intelligence/routes.py').read_text()
    assert "filter_results_target|default('#recommendations-results-content')" in filters
    assert 'hx-target="{{ resolved_results_target }}"' in filters
    assert 'clear_filters_action' in results
    assert "target='#recommendations-workspace-content'" in results
    assert "sync='#recommendations-workspace-content:replace'" in results
    assert "target == 'recommendations-results-content'" in route
    assert 'hx-sync="{{ target }}:replace"' in pagination
    assert "hx_swap='innerHTML show:none focus-scroll:false'" in pagination


def test_restart_list_title_keeps_metrics_in_evidence_not_the_table_title():
    presentation = Path('app/intelligence/finding_presentation.py').read_text()
    assert "rule_key.startswith('kubernetes.pod.high_restart_count')" in presentation
    assert "return f'{count} {resource} in {namespace} {verb} repeated restarts'" in presentation
    assert '(max {' not in presentation


def test_restart_list_title_behavior_excludes_max_restart_metric():
    module = runpy.run_path('app/intelligence/finding_presentation.py')
    title = module['recommendation_table_title'](
        {
            'rule_key': 'kubernetes.pod.high_restart_count:cluster:logging',
            'title': '3 pods in logging have repeated restarts (max 3006)',
            'evidence': {'affected_count': 3, 'namespace': 'logging', 'max_restart_count': 3006},
        }
    )
    assert title == '3 pods in logging have repeated restarts'
    assert '3006' not in title
    assert '(max' not in title
