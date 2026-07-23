from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_disabled_source_does_not_own_primary_scope() -> None:
    source = (ROOT / 'app/integrations/prometheus/binding_management.py').read_text(
        encoding='utf-8'
    )

    assert "IntegrationInstance.provider_type == 'prometheus'" in source
    assert 'IntegrationInstance.enabled.is_(True)' in source


def test_alertmanager_disabled_source_does_not_own_primary_scope() -> None:
    source = (ROOT / 'app/integrations/alertmanager/binding_management.py').read_text(
        encoding='utf-8'
    )

    assert "IntegrationInstance.provider_type == 'alertmanager'" in source
    assert 'IntegrationInstance.enabled.is_(True)' in source
    assert '.join(\n                IntegrationInstance,' in source
