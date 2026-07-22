from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_and_alertmanager_use_same_empty_state_action_label():
    prometheus = (
        ROOT
        / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')
    alertmanager = (
        ROOT
        / 'app/templates/integrations/alertmanager/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    expected = (
        "empty_state_action_label = 'Register Connection' "
        "if empty_state_action_url else none"
    )

    assert expected in prometheus
    assert expected in alertmanager
    assert "empty_state_action_label = 'Register Instance'" not in alertmanager
