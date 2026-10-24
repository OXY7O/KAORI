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
    assert 'xl:max-h-[calc(100vh-12rem)]' in template
    assert 'xl:absolute xl:inset-0 xl:max-h-none' in template
    assert 'max-h-[28rem]' in template
    assert 'shrink-0 border-b border-outline-subtle p-3' in template
    assert 'aria-label="Registered Jobs"' in template
    assert 'x-ref="jobList"' in template
    assert 'overflow-y-auto overscroll-contain' in template
    assert 'data-job-key=' in template
    assert 'x-init="ensureActiveVisible()"' in template
    assert '@popstate.window=' in template
    assert 'hx-push-url="true"' in template
    assert 'hx-target="#job-configuration-workspace"' in template
