import ast
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
STATIC_JS = ROOT / 'app/static/js'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_table_pagination_uses_full_page_and_partial_endpoint_ownership() -> None:
    pagination = read('app/templates/components/pagination.html')
    pagination_js = read('app/static/js/pagination.js')
    record_pagination = read('app/templates/analytics/components/_record_pagination.html')
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert "numeric_pages(current_page, total_pages, page_param='page', hx_target=None, hx_indicator=None, endpoint=None, query_params=None, hx_swap='innerHTML', href_endpoint=None)" in pagination
    assert 'href_endpoint_name = href_endpoint or endpoint_name' in pagination
    assert 'data-page-param="{{ page_param }}"' in pagination
    assert 'container.dataset.pageParam || PAGE_PARAM' in pagination_js
    assert 'replacePage(href, page, pageParam)' in pagination_js
    assert 'partial_endpoint' in record_pagination
    assert 'href_endpoint' in record_pagination
    assert 'Showing <span class="font-semibold text-content-primary">{{ start_item }}</span>–' in record_pagination
    assert 'pagination_ui.resource_name(resource_label, total_rows)' in record_pagination
    assert '>Rows</label>' in record_pagination
    assert 'allowed_per_page=(5, 10, 25, 50)' in record_pagination
    assert "'analytics.workload_tenant_quota'" in tenant
    assert "'analytics.workload_resource_mapping'" in mapping
    assert "'analytics.workload'" in tenant
    assert "'analytics.workload'" in mapping


def test_workload_detail_actions_open_contextual_modals_from_the_action_column() -> None:
    component = read('app/templates/analytics/components/_record_detail_modal.html')
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert 'x-teleport="body"' in component
    assert 'role="dialog"' in component
    assert 'aria-modal="true"' in component
    assert "modal_width = 'max-w-5xl' if size == 'wide' else 'max-w-4xl'" in component
    assert 'max-h-[calc(100dvh-2rem)]' in component
    assert 'relative flex h-[calc(100dvh-1rem)]' not in component
    assert 'overflow-y-auto' in component

    for content in (tenant, mapping):
        assert "evidence_list.header_cell('Action'" in content
        assert 'components/table.html' in content
        assert 'analytics/components/_record_detail_modal.html' in content
        assert 'record_detail_modal.render' in content
        assert "size='wide'" in content
        assert 'table_ui.action_classes()' in content
        assert 'w-full whitespace-nowrap sm:w-auto' in content
        assert 'aria-haspopup="dialog"' in content
        assert 'data-lucide="panel-top-open"' in content
        assert '<span>View More</span>' in content
        assert 'x-data="{ detailOpen: false }"' in content
        assert '@click="detailOpen = true"' in content
        assert 'expanded ?' not in content
        assert 'data-lucide="chevron-down"' not in content
        assert 'class="border-t border-outline-subtle bg-surface-subtle px-4 py-4"' not in content

    assert 'aria-controls="tenant-quota-modal-{{ loop.index }}"' in tenant
    assert "'tenant-quota-modal-' ~ loop.index" in tenant
    assert 'ResourceQuota Object Evidence' in tenant
    assert 'Effective CPU Boundary' in tenant
    assert 'Effective Memory Boundary' in tenant

    assert 'aria-controls="workload-mapping-modal-{{ loop.index }}"' in mapping
    assert "'workload-mapping-modal-' ~ loop.index" in mapping
    assert 'CPU Request and Limit Profile' in mapping
    assert 'Memory Request and Limit Profile' in mapping
    assert 'Pod Membership' in mapping


def test_workload_overview_uses_compact_metric_strip_and_scope_context() -> None:
    overview = read('app/templates/analytics/workload/partials/_overview.html')

    assert 'Operational Workload Posture' in overview
    assert 'Analysis Context' in overview
    assert 'Active Scope' in overview
    assert 'Quota Coverage' in overview
    assert 'Request Coverage' in overview
    assert 'BestEffort Workloads' in overview
    assert 'High-Risk Workloads' in overview
    assert 'Operational Reading' in overview
    assert 'analysis_surface.evidence_shell_classes' in overview
    assert 'card=true' in overview
    assert 'text-[' not in overview
    assert 'tracking-[' not in overview


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
        assert 'data-page-size="3"' in content
        assert 'data-kaori-recommendation-item' in content
        assert 'loop.index > 3' in content
        assert 'recommendation_pager.controls' in content
        assert ", 3)" in content

    pager = read('app/templates/components/recommendation_pager.html')
    pager_js = read('app/static/js/recommendation_pagination.js')
    layout = read('app/templates/layouts/app.html')

    assert "controls(total_items, item_label='Recommendations', page_size=3)" in pager
    assert '{% if normalized_total > 0 %}' in pager
    assert 'normalized_total > page_size' not in pager
    assert 'flex items-center justify-between gap-3' in pager
    assert 'data-recommendation-previous' in pager
    assert 'data-recommendation-next' in pager
    assert 'Page <span class="text-content-primary" data-recommendation-page>1</span>' in pager
    assert 'data-recommendation-start' not in pager
    assert 'data-recommendation-end' not in pager
    assert 'data-recommendation-total>' not in pager
    assert "const ROOT_SELECTOR = '[data-kaori-recommendation-pager]'" in pager_js
    assert 'numberValue(root.dataset.pageSize, 3)' in pager_js
    assert "document.addEventListener('htmx:afterSwap'" in pager_js
    assert 'data-recommendation-start' not in pager_js
    assert 'data-recommendation-end' not in pager_js
    assert "querySelector('[data-recommendation-total]')" not in pager_js
    assert "filename='js/recommendation_pagination.js'" in layout



def test_recommendation_pager_remains_visible_on_a_single_page() -> None:
    environment = Environment(loader=FileSystemLoader(TEMPLATES))
    template = environment.from_string(
        "{% import 'components/recommendation_pager.html' as pager %}"
        "{{ pager.controls(3, 'Recommendations', 3) }}"
    )

    rendered = template.render()

    assert 'data-recommendation-previous' in rendered
    assert 'data-recommendation-next' in rendered
    assert 'Page <span class="text-content-primary" data-recommendation-page>1</span>' in rendered
    assert 'data-recommendation-next' in rendered and 'disabled' in rendered


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
        'app/templates/analytics/components/_record_detail_modal.html',
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
