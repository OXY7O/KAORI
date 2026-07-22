from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESENTATION = ROOT / 'app/prometheus/presentation.py'
ROUTES = ROOT / 'app/prometheus/routes.py'
RUNTIME_OWNER = ROOT / 'app/templates/prometheus/partials/_detail_runtime.html'
SHARED_HISTORY = ROOT / 'app/templates/integrations/partials/_runtime_history.html'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_prometheus_runtime_history_uses_canonical_endpoint() -> None:
    presentation = _read(PRESENTATION)
    routes = _read(ROUTES)
    owner = _read(RUNTIME_OWNER)
    assert 'def instance_runtime_history(' in routes
    assert "url_for('prometheus.instance_runtime_history', instance_id=instance.id)" in presentation
    assert "url_for('prometheus.instance_runtime_history', instance_id=instance.id)" in owner
    assert "integrations/partials/_runtime_history.html" in owner
    assert 'Recent Runtime Observations' in _read(SHARED_HISTORY)


def test_retired_runtime_history_endpoint_and_wrapper_are_removed() -> None:
    sources = '\n'.join((_read(PRESENTATION), _read(ROUTES), _read(RUNTIME_OWNER)))
    assert 'prometheus.runtime_history' not in sources
    assert not (ROOT / 'app/templates/prometheus/partials/_runtime_history.html').exists()
