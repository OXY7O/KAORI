from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
PROM_ROUTES = ROOT / 'app/prometheus/routes.py'
DEPENDENCIES = ROOT / 'app/common/dependencies.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_prometheus_hero_uses_mandatory_capability_context() -> None:
    detail = read(PROM_DETAIL)
    assert 'stats.capabilities' not in detail
    assert 'capability_summary.observed|default(0)' in detail


def test_retired_prometheus_bookmark_routes_are_not_registered() -> None:
    routes = read(PROM_ROUTES)
    assert "@prometheus_bp.get('/instances')" not in routes
    assert "/instances/<int:instance_id>/edit" not in routes
    assert "/cluster/<string:cluster_id>" not in routes
    assert "@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])" in routes


