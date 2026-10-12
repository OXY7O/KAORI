from __future__ import annotations

from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.artifact_registry import presentation_common


@pytest.mark.parametrize('requested_id', [9, 0, -1])
def test_unavailable_registry_overview_scope_does_not_fall_through_to_all(
    monkeypatch, requested_id: int,
) -> None:
    provider = SimpleNamespace(id=1, name='Enabled Registry')
    monkeypatch.setattr(presentation_common, '_providers', lambda: [provider])
    # No RegistryCollectionState read can occur until scope membership is validated.
    with pytest.raises(NotFound):
        presentation_common._overview_scope_context(provider_id=requested_id)


def test_registry_overview_does_not_admit_disabled_active_integrations() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] /
        'app/artifact_registry/presentation_common.py'
    ).read_text(encoding='utf-8')
    providers = source.split('def _providers(', 1)[1].split('@overload', 1)[0]
    assert "IntegrationInstance.integration_type == 'registry'" in providers
    assert "IntegrationInstance.lifecycle_status == 'active'" in providers
    assert 'IntegrationInstance.enabled.is_(True)' in providers
    assert 'raise NotFound(' in source
