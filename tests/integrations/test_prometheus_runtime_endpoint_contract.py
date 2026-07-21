from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRESENTATION = ROOT / 'app/prometheus/presentation.py'
ROUTES = ROOT / 'app/prometheus/routes.py'
RUNTIME_HISTORY_TEMPLATE = ROOT / 'app/templates/prometheus/partials/_runtime_history.html'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_prometheus_runtime_history_uses_canonical_endpoint() -> None:
    presentation = _read(PRESENTATION)
    routes = _read(ROUTES)
    template = _read(RUNTIME_HISTORY_TEMPLATE)

    assert "def instance_runtime_history(" in routes
    assert "url_for('prometheus.instance_runtime_history', instance_id=instance.id)" in presentation
    assert "url_for('prometheus.instance_runtime_history', instance_id=instance.id)" in template


def test_prometheus_legacy_runtime_history_endpoint_is_removed() -> None:
    sources = '\n'.join(
        (
            _read(PRESENTATION),
            _read(ROUTES),
            _read(RUNTIME_HISTORY_TEMPLATE),
        )
    )

    assert "prometheus.runtime_history" not in sources
