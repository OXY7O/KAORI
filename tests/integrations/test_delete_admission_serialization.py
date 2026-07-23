from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.validation import web


@pytest.mark.parametrize(
    ('provider_type', 'model_name'),
    (
        ('prometheus', 'PrometheusInstance'),
        ('alertmanager', 'AlertmanagerInstance'),
        ('kubernetes', 'KubernetesConnection'),
    ),
)
def test_provider_admission_rejects_deleted_target(monkeypatch, provider_type: str, model_name: str) -> None:
    seen: list[tuple[object, int]] = []

    def fake_get(model: object, instance_id: int):
        seen.append((model, instance_id))
        return None

    monkeypatch.setattr(web.db.session, 'get', fake_get)

    with pytest.raises(RuntimeError, match='deleted before KAORI could admit the job'):
        web._assert_provider_target_exists(provider_type=provider_type, instance_id=41)

    assert seen[0][0].__name__ == model_name
    assert seen[0][1] == 41


def test_provider_admission_accepts_existing_target(monkeypatch) -> None:
    target = SimpleNamespace(id=7)
    monkeypatch.setattr(web.db.session, 'get', lambda model, instance_id: target)

    assert web._assert_provider_target_exists(provider_type='prometheus', instance_id=7) is None
