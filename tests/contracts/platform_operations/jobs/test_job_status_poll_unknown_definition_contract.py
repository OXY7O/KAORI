from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_configuration_status_poll_reuses_registered_job_404_boundary() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')
    block = routes.split('def configuration_status(job_key: str)', 1)[1].split('@bp.post(', 1)[0]
    assert '_get_job_definition_or_404(job_key)' in block
    assert block.index('_get_job_definition_or_404(job_key)') < block.index('_configuration_live_context(job_key)')


def test_unknown_definition_still_maps_to_http_404() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')
    lookup = routes.split('def _get_job_definition_or_404(', 1)[1].split('def _configuration_context(', 1)[0]
    assert 'except LookupError:' in lookup
    assert 'abort(404)' in lookup
