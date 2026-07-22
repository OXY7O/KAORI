from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_and_alertmanager_use_connections_in_registry_footer():
    prometheus = (
        ROOT
        / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')
    alertmanager = (
        ROOT
        / 'app/templates/integrations/alertmanager/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    assert 'pagination.total_items }}</strong> connections' in prometheus
    assert 'pagination.total_items }}</span> connections' in alertmanager
    assert 'instances' not in alertmanager.split('Showing', 1)[1].split('</div>', 1)[0]
