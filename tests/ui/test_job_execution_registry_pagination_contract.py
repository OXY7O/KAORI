from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'app/templates/integrations/jobs/partials/_registry.html'


def source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_jobs_registry_uses_supported_shared_pagination_helpers() -> None:
    template = source()
    assert 'pagination_ui.page_classes' not in template
    assert 'pagination_ui.numeric_pages(job_pagination.page, job_pagination.total_pages)' in template
    assert 'pagination_ui.page_size_classes()' in template


def test_jobs_registry_previous_next_follow_kaori_contract() -> None:
    template = source()
    assert 'pagination_ui.navigation_classes(disabled=false)' in template
    assert 'pagination_ui.navigation_classes(disabled=true)' in template
    assert 'data-lucide="chevron-left"' in template
    assert 'data-lucide="chevron-right"' in template
    assert 'aria-disabled="true"' in template


def test_jobs_page_size_change_resets_to_first_page_and_preserves_filters() -> None:
    template = source()
    assert '<input type="hidden" name="page" value="1">' in template
    for field in ('status', 'workload', 'queue', 'search'):
        assert f'name="{field}"' in template
    assert 'onchange="this.form.requestSubmit()"' in template
