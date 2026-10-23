"""UI contract for the compact Data Lifecycle domain selector (#2915).

Source/render syntax assertions complement, not replace, DevContainer
keyboard/HTMX/mobile/light-dark Visual QA and human acceptance.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / 'app/templates/platform_operations/data_lifecycle/index.html'


def read() -> str:
    return INDEX.read_text(encoding='utf-8')


def test_navigator_template_has_valid_jinja_and_keeps_shared_workspace() -> None:
    source = read()
    Environment().parse(source)
    assert 'components/framed_workspace_tabs.html' in source
    assert 'framed_workspace_tabs.render_navigation(' in source
    assert 'components/table_label.html' in source
    assert 'components/info_tip.html' in source
    assert 'xl:grid-cols-12 xl:items-stretch' in source
    assert 'xl:col-span-4' in source
    assert '<main class="min-w-0 xl:col-span-8">' in source
    assert 'platform_operations/data_lifecycle/partials/_domain_workspace.html' in source
    assert '{% for domain in lifecycle.domains %}' in source


def test_search_header_and_execution_footer_stay_outside_scroll_region() -> None:
    source = read()
    search = source.index('id="data-lifecycle-domain-search"')
    list_start = source.index('x-ref="domainList"')
    footer = source.index('<footer class="flex flex-wrap items-center')
    assert search < list_start < footer
    assert 'xl:h-full xl:overflow-y-auto xl:overscroll-contain' in source
    assert 'xl:!flex xl:min-h-0 xl:flex-1 xl:flex-col' in source
    assert 'Search Data Domains' in source
    assert 'visibleDomainCount' in source
    assert 'No matching domains' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source


def test_compact_domain_rows_preserve_navigation_state_and_accessibility() -> None:
    source = read()
    assert "domainSearch.trim().toLowerCase()" in source
    assert "item.dataset.domainSearch.includes(query)" in source
    assert 'data-domain-search="{{ (domain.label ~ ' in source
    assert 'domain.hot_retention_days' in source
    assert 'domain.total_archives' in source
    assert 'line-clamp-1' in source
    assert "table_label.status_label('Enabled' if domain.enabled else 'Disabled'" in source
    assert 'hx-target="#data-lifecycle-domain-workspace"' in source
    assert 'hx-push-url="true"' in source
    assert ':aria-current="activeDomain ===' in source
    assert 'focus-visible:ring-outline-focus' in source
    assert 'href="{{ url_for(\'platform_operations.data_lifecycle.index\'' in source
    assert 'domainPickerOpen = false' in source


def test_mobile_disclosure_has_readable_no_js_fallback() -> None:
    source = read()
    assert 'aria-controls="data-lifecycle-domain-picker"' in source
    assert 'id="data-lifecycle-domain-picker"' in source
    assert ':aria-expanded="String(domainPickerOpen)"' in source
    assert 'x-show="domainPickerOpen"' in source
    assert 'xl:!flex xl:min-h-0 xl:flex-1 xl:flex-col' in source
    assert '@click="domainPickerOpen = !domainPickerOpen"' in source
    # Do not use x-cloak: absent JS must leave direct href navigation usable.
    assert 'x-cloak' not in source


def test_execution_boundary_uses_canonical_guide_and_permission_scoped_jobs_link() -> None:
    source = read()
    assert "info_tip.render('data-lifecycle-execution-boundary'," in source
    guide = source.split("info_tip.render('data-lifecycle-execution-boundary',", 1)[1].split('}}', 1)[0]
    assert "variant='guide'" in guide
    assert "placement='right'" in guide
    assert 'Lifecycle policy and archive evidence stay in Data Lifecycle.' in source
    assert 'Execution Boundary' in source
    assert "{% if current_user.has_permission('jobs.view') %}" in source
    assert "url_for('jobs.executions')" in source
    assert 'Open Jobs &amp; Executions' in source


def test_desktop_nav_is_height_matched_to_policy_without_scroll_driving_grid_height() -> None:
    source = read()
    assert 'xl:grid-cols-12 xl:items-stretch' in source
    assert 'xl:relative xl:col-span-4 xl:min-h-[25rem]' in source
    assert 'xl:absolute xl:inset-0 xl:flex xl:flex-col' in source
    assert 'xl:!flex xl:min-h-0 xl:flex-1 xl:flex-col' in source
    assert 'xl:min-h-0 xl:flex-1 xl:overflow-hidden' in source
    assert 'xl:h-full xl:overflow-y-auto xl:overscroll-contain' in source
    assert 'xl:shrink-0' in source
    assert 'xl:max-h-[min(65dvh,36rem)]' not in source
    assert 'xl:col-span-8' in source
    assert '<main class="min-w-0 xl:col-span-8">' in source


def test_current_domain_scroll_restoration_does_not_scroll_outer_document() -> None:
    source = read()
    assert 'x-init="ensureActiveVisible()"' in source
    assert '@popstate.window=' in source
    assert "new URLSearchParams(window.location.search).get('domain')" in source
    assert 'data-domain-id="{{ domain.name }}"' in source
    assert 'ensureActiveVisible() {' in source
    assert 'if (!list || list.scrollHeight <= list.clientHeight) return;' in source
    assert "item.dataset.domainId === this.activeDomain" in source
    assert 'list.getBoundingClientRect()' in source
    assert 'active.getBoundingClientRect()' in source
    assert 'list.scrollTop +=' in source
    assert 'window.scrollTo' not in source
    assert 'scrollIntoView' not in source
    assert '@click="activeDomain =' in source


def test_compact_footer_and_search_are_anchored_above_and_below_only_list() -> None:
    source = read()
    left = source.split('<aside class="min-w-0 xl:relative', 1)[1].split(
        '</aside>', 1,
    )[0]
    search = left.index('id="data-lifecycle-domain-search"')
    list_start = left.index('x-ref="domainList"')
    list_end = left.index('</nav>')
    footer = left.index('<footer class="flex flex-wrap items-center')
    assert search < list_start < list_end < footer
    assert "info_tip.render('data-lifecycle-execution-boundary'," in left
    assert "current_user.has_permission('jobs.view')" in left
    assert 'xl:overflow-y-auto' not in left[:list_start]
    assert 'xl:overflow-y-auto' not in left[list_end:]
