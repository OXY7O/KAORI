"""Analytics eligibility uses committed resolver failure contracts, not catch-all success."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.kubernetes.analytics import job_adapter
from app.models.cluster import Cluster


def _cluster() -> Cluster:
    return cast(Cluster, SimpleNamespace(id=17, name='Review Cluster'))


def _raises(error: Exception) -> Callable[..., None]:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise error

    return unavailable


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('canonical database unavailable'),
        RuntimeError('missing Flask context'),
        ValueError('invalid resolver evidence'),
        TypeError('invalid resolver snapshot'),
    ],
)
def test_metrics_dataset_known_resolution_failure_denies_eligibility(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(job_adapter, 'resolve_metrics_sources', _raises(error))
    diagnostics: list[str] = []

    result = job_adapter._metrics_source_dataset_eligible(
        _cluster(), job_adapter.CAPACITY_DATASET_KEY, diagnostics
    )

    assert result is False
    assert any('source resolution failed' in item for item in diagnostics)


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('canonical database unavailable'),
        RuntimeError('missing Flask context'),
        ValueError('invalid resolver evidence'),
        TypeError('invalid resolver snapshot'),
    ],
)
@pytest.mark.parametrize('source', ['alertmanager', 'metrics_source'])
def test_alert_dataset_known_resolution_failure_denies_eligibility(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    source: str,
) -> None:
    if source == 'alertmanager':
        monkeypatch.setattr(job_adapter, 'resolve_alertmanager_sources', _raises(error))
    else:
        monkeypatch.setattr(job_adapter, 'resolve_metrics_sources', _raises(error))
    diagnostics: list[str] = []

    result = job_adapter._alert_dataset_eligible(
        _cluster(), 'analytics.alerts', {'source': source}, diagnostics
    )

    assert result is False
    assert any('resolution failed' in item for item in diagnostics)


def test_unexpected_metrics_resolution_bug_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_adapter, 'resolve_metrics_sources', _raises(LookupError('unexpected defect')))

    with pytest.raises(LookupError, match='unexpected defect'):
        job_adapter._metrics_source_dataset_eligible(_cluster(), job_adapter.CAPACITY_DATASET_KEY)


@pytest.mark.parametrize('source', ['alertmanager', 'metrics_source'])
def test_unexpected_alert_resolution_bug_propagates(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    if source == 'alertmanager':
        monkeypatch.setattr(job_adapter, 'resolve_alertmanager_sources', _raises(LookupError('unexpected defect')))
    else:
        monkeypatch.setattr(job_adapter, 'resolve_metrics_sources', _raises(LookupError('unexpected defect')))

    with pytest.raises(LookupError, match='unexpected defect'):
        job_adapter._alert_dataset_eligible(_cluster(), 'analytics.alerts', {'source': source})


def test_eligible_metrics_binding_remains_admissible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        job_adapter,
        'resolve_metrics_sources',
        lambda **_kwargs: SimpleNamespace(selected=object(), candidates=()),
    )

    assert job_adapter._metrics_source_dataset_eligible(_cluster(), job_adapter.CAPACITY_DATASET_KEY) is True


@pytest.mark.parametrize('source', ['alertmanager', 'metrics_source'])
def test_eligible_alert_binding_remains_admissible(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    def candidate(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(selected=object(), candidates=())
    if source == 'alertmanager':
        monkeypatch.setattr(job_adapter, 'resolve_alertmanager_sources', candidate)
    else:
        monkeypatch.setattr(job_adapter, 'resolve_metrics_sources', candidate)

    assert job_adapter._alert_dataset_eligible(_cluster(), 'analytics.alerts', {'source': source}) is True
