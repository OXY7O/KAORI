from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_job_catalog_search_has_native_label_and_input_association() -> None:
    template = (ROOT / 'app/templates/platform_operations/jobs/configuration/_workspace.html').read_text(
        encoding='utf-8'
    )
    assert 'for="job-configuration-catalog-search"' in template
    # HTML attributes may wrap across lines while native label association stays intact.
    assert 'id="job-configuration-catalog-search"' in template
    assert 'type="search"' in template
    assert template.count('id="job-configuration-catalog-search"') == 1
    assert 'data-job-search' in template
    assert '@input=' in template


def test_registered_jobs_catalog_scrolls_independently_like_data_lifecycle() -> None:
    template = (ROOT / 'app/templates/platform_operations/jobs/configuration/_workspace.html').read_text(
        encoding='utf-8'
    )
    assert 'xl:items-stretch' in template
    assert 'xl:relative xl:col-span-4' in template
    assert 'xl:max-h-[calc(100vh-12rem)]' not in template
    assert 'xl:absolute xl:inset-0 xl:max-h-none' in template
    assert 'max-h-[28rem]' in template
    assert 'xl:absolute xl:inset-0 xl:max-h-none' in template
    assert 'shrink-0 border-b border-outline-subtle p-3' in template
    assert 'footer class="flex shrink-0 items-center justify-between gap-2' in template
    footer = template.split('<footer ', 1)[1].split('</footer>', 1)[0]
    assert 'overflow-x-auto' not in footer
    assert 'overflow-y-auto' not in footer
    assert 'whitespace-nowrap' in footer
    assert '<span class="sr-only">Jobs shown:</span>' in footer
    assert 'aria-label="Open Jobs & Executions"' in footer
    assert 'visibleJobCount' in template
    assert 'x-text="visibleJobCount"' in template
    assert 'No matching jobs' in template
    assert 'title="{{ item.name }}">{{ item.name }}' in template
    assert 'mt-1.5 flex min-w-0 items-center' in template
    assert 'title="{{ item.queue_name }}">{{ item.queue_name }}' in template
    assert 'id="job-catalog-status-' in template
    assert 'id="job-catalog-activity-' in template
    assert 'line-clamp-1 text-xs leading-5' not in template
    assert '{{ item.catalog_summary }}' not in template
    assert '<p class="mt-0.5 text-xs font-semibold text-content-muted">{{ item.domain }}</p>' not in template
    assert "variant='guide'" in template
    assert 'aria-label="Registered Jobs"' in template
    assert 'x-ref="jobList"' in template
    assert 'overflow-y-auto overscroll-contain' in template
    assert 'data-job-key=' in template
    assert 'x-init="ensureActiveVisible()"' in template
    assert '@popstate.window=' in template
    assert 'hx-push-url="true"' in template
    assert 'hx-target="#job-configuration-workspace"' in template


def test_catalog_search_preserves_authoritative_job_descriptions() -> None:
    template = (ROOT / 'app/templates/platform_operations/jobs/configuration/_workspace.html').read_text(
        encoding='utf-8'
    )
    source = (ROOT / 'app/platform_operations/jobs/configuration.py').read_text(encoding='utf-8')
    catalog = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text(
        encoding='utf-8'
    )

    assert "item.description ~ ' ' ~ item.queue_name" in template
    assert "'description': definition.description" in source
    assert "'domain': definition.domain" in source
    assert "'catalog_summary':" not in source
    assert '_CATALOG_SUMMARIES' not in source
    assert template.count('[data-job-catalog-row]') == 2
    assert 'data-job-catalog-row\n' in template
    registered_keys = [line for line in catalog.splitlines() if line.startswith('- key: ')]
    assert len(registered_keys) == 19
