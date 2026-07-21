from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'app/integrations/validation/tasks.py'
PRESENTATION = ROOT / 'app/jobs/presentation.py'
ACTIVE = ROOT / 'app/templates/integrations/jobs/partials/_active_jobs.html'
REGISTRY = ROOT / 'app/templates/integrations/jobs/partials/_registry.html'
ROUTES = ROOT / 'app/integrations/routes.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_integration_workers_publish_phase_progress() -> None:
    source = read(TASKS)
    assert 'def _update_worker_phase' in source
    assert "current=1, total=4" in source
    assert "current=2, total=4" in source
    assert "current=3, total=4" in source
    assert "current=1, total=3" in source
    assert "current=2, total=3" in source


def test_unknown_active_progress_is_indeterminate_not_false_zero_percent() -> None:
    presentation = read(PRESENTATION)
    active = read(ACTIVE)
    registry = read(REGISTRY)
    assert "progress_mode = 'indeterminate'" in presentation
    assert "progress_label = 'In Progress'" in presentation
    assert "progress_label = 'Queued'" in presentation
    assert 'notification-progress-indeterminate' in active
    assert 'notification-progress-indeterminate' in registry
    assert '{{ row.progress_label }}' in active
    assert '{{ row.progress_label }}' in registry


def test_active_work_refreshes_as_a_dedicated_htmx_fragment() -> None:
    routes = read(ROUTES)
    active = read(ACTIVE)
    assert "if fragment == 'active'" in routes
    assert "_active_jobs.html" in routes
    assert 'hx-trigger="every 5s"' in active
    assert "fragment='active'" in active
