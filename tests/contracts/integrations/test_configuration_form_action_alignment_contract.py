from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTION_BAR = ROOT / 'app/templates/components/form_action_bar.html'
PROM = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
ALERT = ROOT / 'app/templates/alertmanager/partials/_detail_configuration.html'
DECISION = ROOT / 'app/templates/integrations/components/_configuration_decision.html'


def test_configuration_actions_use_integrated_shared_footer() -> None:
    shared = ACTION_BAR.read_text()
    assert 'embedded=false' in shared
    assert 'border-t border-outline-subtle bg-surface-subtle' in shared
    for path in (PROM, ALERT):
        source = path.read_text()
        assert 'embedded=true' in source
        assert 'items-stretch' in source
        assert 'flex h-full flex-col' in source


def test_configuration_decision_matches_form_height_without_sticky_drift() -> None:
    source = DECISION.read_text()
    assert 'flex h-full min-h-full flex-col self-stretch' in source
    assert 'xl:sticky' not in source
    assert 'flex-1 border-b border-outline-subtle' in source
