"""Optional committed snapshot calls use typed, auditable error boundaries."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.kubernetes.analytics.overview import schema as overview_schema
from app.kubernetes.analytics.overview import service as overview_service

_MODULE = 'app.kubernetes.analytics.overview.schema'
_FUNCTION = '_kaori_test_optional_snapshot'


def _set_presenter(monkeypatch: pytest.MonkeyPatch, presenter: Callable[..., object]) -> None:
    monkeypatch.setattr(overview_schema, _FUNCTION, presenter, raising=False)


def _call_presenter() -> dict[str, object] | None:
    return overview_service._call_optional_snapshot(
        module_path=_MODULE,
        function_names=[_FUNCTION],
        cluster_id='17',
    )


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('durable snapshot unavailable'),
        RuntimeError('missing Flask app context'),
        TypeError('invalid snapshot argument'),
        ValueError('invalid snapshot value'),
        KeyError('missing committed evidence'),
    ],
)
def test_expected_keyword_presenter_failure_falls_back(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise error

    _set_presenter(monkeypatch, broken)

    with Flask(__name__).app_context():
        assert _call_presenter() is None


def test_expected_positional_presenter_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def positional(*_args: object, **kwargs: object) -> None:
        if kwargs:
            raise TypeError('positional signature required')
        raise ValueError('invalid positional evidence')

    _set_presenter(monkeypatch, positional)

    with Flask(__name__).app_context():
        assert _call_presenter() is None


def test_unexpected_keyword_presenter_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise LookupError('unexpected presenter defect')

    _set_presenter(monkeypatch, broken)

    with pytest.raises(LookupError, match='unexpected presenter defect'):
        _call_presenter()


def test_unexpected_positional_presenter_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def positional(*_args: object, **kwargs: object) -> None:
        if kwargs:
            raise TypeError('positional signature required')
        raise LookupError('unexpected positional defect')

    _set_presenter(monkeypatch, positional)

    with pytest.raises(LookupError, match='unexpected positional defect'):
        _call_presenter()


def test_healthy_keyword_presenter_remains_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_presenter(monkeypatch, lambda **_kwargs: {'source': 'committed', 'ready': True})

    assert _call_presenter() == {'source': 'committed', 'ready': True}
