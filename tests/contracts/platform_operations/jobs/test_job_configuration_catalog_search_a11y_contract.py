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
