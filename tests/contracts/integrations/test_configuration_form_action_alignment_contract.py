from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROM = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
ALERT = ROOT / 'app/templates/alertmanager/partials/_detail_configuration.html'
SHARED = ROOT / 'app/templates/integrations/components/_provider_configuration_contract.html'


def test_configuration_tabs_use_shared_read_only_contract_footer() -> None:
    shared = SHARED.read_text()
    assert 'data-kaori-provider-configuration-contract' in shared
    assert 'Configure Connection' in shared
    assert 'border-t border-outline-subtle bg-surface-subtle' in shared
    for path in (PROM, ALERT):
        source = path.read_text()
        assert 'provider_configuration_contract.render(' in source
        assert 'form_action_bar.render(' not in source
