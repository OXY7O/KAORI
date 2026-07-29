import ast
import re
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
STATIC_JS = ROOT / 'app/static/js'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_numeric_pagination_supports_endpoint_specific_page_parameters() -> None:
    pagination = read('app/templates/components/pagination.html')
    pagination_js = read('app/static/js/pagination.js')
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert "numeric_pages(current_page, total_pages, page_param='page')" in pagination
    assert 'data-page-param="{{ page_param }}"' in pagination
    assert 'container.dataset.pageParam || PAGE_PARAM' in pagination_js
    assert 'replacePage(href, page, pageParam)' in pagination_js
    assert 'data-kaori-generated-page' in pagination_js
    assert "numeric_pages(quota_pagination.page, quota_pagination.total_pages, 'quota_page')" in tenant
    assert "numeric_pages(workload_pagination.page, workload_pagination.total_pages, 'workload_page')" in mapping


def test_workload_detail_actions_use_full_width_accordion_rails() -> None:
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert '>Action</div>' not in tenant
    assert '>Action</div>' not in mapping
    assert "expanded ? 'Hide Quota Details' : 'View Quota Details'" in tenant
    assert 'aria-controls="tenant-quota-details-{{ loop.index }}"' in tenant
    assert 'CPU, Memory, Governance &amp; Recommendation' in tenant
    assert "expanded ? 'Hide Resource Details' : 'View Resource Details'" in mapping
    assert 'aria-controls="workload-mapping-details-{{ loop.index }}"' in mapping
    assert 'Requests, Limits, Usage, QoS &amp; Pods' in mapping
    assert 'class="group flex w-full items-center gap-3 border-t' in tenant
    assert 'class="group flex w-full items-center gap-3 border-t' in mapping


def test_workload_overview_uses_compact_metric_strip_and_scope_context() -> None:
    overview = read('app/templates/analytics/workload/partials/_overview.html')

    assert 'Operational Workload Posture' in overview
    assert 'Analysis Context' in overview
    assert 'Active Scope' in overview
    assert 'divide-y divide-outline-subtle overflow-hidden rounded-lg border' in overview
    assert "finding_count_display ~ ' Findings'" in overview
    assert "recommendation_count_display ~ ' Recommendations'" in overview
    assert 'bg-surface-hover p-4' not in overview


def test_kubernetes_analytics_recommendation_lists_use_simple_previous_next_pager() -> None:
    recommendation_templates = (
        'app/templates/analytics/overview/partials/_recommendations.html',
        'app/templates/analytics/workload/partials/_recommendations.html',
        'app/templates/analytics/utilization/partials/_recommendations.html',
        'app/templates/analytics/capacity/partials/_recommendations.html',
        'app/templates/analytics/storage/partials/_recommendations.html',
        'app/templates/analytics/alerts/partials/_recommendations.html',
        'app/templates/analytics/forecast/partials/_forecast_section.html',
        'app/templates/analytics/top_consumers/partials/_top_consumers_section.html',
    )

    for relative in recommendation_templates:
        content = read(relative)
        assert 'components/recommendation_pager.html' in content
        assert 'data-kaori-recommendation-pager' in content
        assert 'data-kaori-recommendation-item' in content
        assert 'recommendation_pager.controls' in content

    pager = read('app/templates/components/recommendation_pager.html')
    pager_js = read('app/static/js/recommendation_pagination.js')
    layout = read('app/templates/layouts/app.html')

    assert 'data-recommendation-previous' in pager
    assert 'data-recommendation-next' in pager
    assert 'Page&nbsp;' in pager
    assert "const ROOT_SELECTOR = '[data-kaori-recommendation-pager]'" in pager_js
    assert "document.addEventListener('htmx:afterSwap'" in pager_js
    assert "filename='js/recommendation_pagination.js'" in layout


def test_intelligence_recommendations_use_simple_server_side_previous_next_pagination() -> None:
    template = read('app/templates/intelligence/recommendations.html')

    assert 'pagination_ui.numeric_pages' not in template
    assert 'Page {{ payload.pagination.page }} of {{ payload.pagination.total_pages }}' in template
    assert '{% if payload.pagination.has_prev %}' in template
    assert '{% if payload.pagination.has_next %}' in template
    assert 'recommendation-pagination-size' not in template


def test_recommendation_titles_and_workspace_labels_are_title_case() -> None:
    catalog = read('app/intelligence/catalog.py')
    service = read('app/intelligence/service.py')
    template = read('app/templates/intelligence/recommendations.html')

    for title in (
        'Workloads Without CPU Requests',
        'Workloads Without Memory Requests',
        'Container Image Uses Latest Tag',
        'Namespace Without Resource Quota',
        'TLS Secret Certificate Expiring Soon',
        'Persistent Volume Near Capacity Enrichment',
        'VM CPU Appears Over-Provisioned',
        'Pods With High Restart Count',
        'Node Is Not Ready',
        'Storage Object Needs Binding Review',
    ):
        assert title in catalog

    assert "'hero_label': 'Infrastructure Intelligence'" in service
    assert "'engine_status': 'Signal-Based Guidance'" in service
    assert 'Intelligence Posture' in template
    assert 'Recommendation Registry' in template
    assert '{{ payload.page_title }} Data Workspace' in template
    assert 'Affected Asset' in template
    assert 'Recommended Action' in template
    assert 'Supported Sources' in template


def test_kubernetes_recommendation_title_literals_follow_title_case() -> None:
    source_files = (
        'app/intelligence/recommendation_engine.py',
        'app/intelligence/catalog.py',
        'app/analytics/capacity/service.py',
        'app/analytics/top_consumers/service.py',
        'app/analytics/workload/service.py',
        'app/analytics/alerts/application.py',
        'app/analytics/forecast/service.py',
        'app/analytics/utilization/materialization.py',
    )
    minor_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from', 'in',
        'nor', 'of', 'on', 'or', 'per', 'the', 'to', 'via', 'with', 'without',
    }
    titles: list[tuple[str, int, str]] = []

    for relative in source_files:
        tree = ast.parse(read(relative))
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Call):
                candidates.extend(
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg in {'title', 'default_title'}
                )
            elif isinstance(node, ast.Dict):
                candidates.extend(
                    value
                    for key, value in zip(node.keys, node.values, strict=False)
                    if isinstance(key, ast.Constant) and key.value == 'title'
                )

            for candidate in candidates:
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    titles.append((relative, candidate.lineno, candidate.value))

    failures = []
    for relative, line, title in titles:
        words = re.findall(r'[A-Za-z][A-Za-z]*(?:-[A-Za-z]+)*', title)
        for index, word in enumerate(words):
            if 0 < index < len(words) - 1 and word.lower() in minor_words:
                continue
            if not all(part[:1].isupper() for part in word.split('-')):
                failures.append(f'{relative}:{line}: {title}')
                break

    assert not failures, '\n'.join(failures)


def test_changed_templates_parse() -> None:
    environment = Environment()
    changed_templates = (
        'app/templates/components/pagination.html',
        'app/templates/components/recommendation_pager.html',
        'app/templates/analytics/workload/partials/_overview.html',
        'app/templates/analytics/workload/partials/_tenant_quota_section.html',
        'app/templates/analytics/workload/partials/_workload_mapping_section.html',
        'app/templates/analytics/workload/partials/_recommendations.html',
        'app/templates/analytics/utilization/partials/_recommendations.html',
        'app/templates/analytics/capacity/partials/_recommendations.html',
        'app/templates/analytics/storage/partials/_recommendations.html',
        'app/templates/analytics/alerts/partials/_recommendations.html',
        'app/templates/analytics/forecast/partials/_forecast_section.html',
        'app/templates/analytics/top_consumers/partials/_top_consumers_section.html',
        'app/templates/analytics/overview/partials/_recommendations.html',
        'app/templates/intelligence/recommendations.html',
        'app/templates/layouts/app.html',
    )

    for relative in changed_templates:
        environment.parse(read(relative))
