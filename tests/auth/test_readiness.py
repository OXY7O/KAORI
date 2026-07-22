from __future__ import annotations

from types import SimpleNamespace

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.auth import readiness


def test_authentication_readiness_requires_all_login_persistence_tables(monkeypatch) -> None:
    available = {'users', 'roles', 'permissions', 'identity_providers'}
    monkeypatch.setattr(readiness, 'inspect', lambda _engine: SimpleNamespace(get_table_names=lambda: list(available)))
    monkeypatch.setattr(readiness, 'db', SimpleNamespace(engine=object()))

    with Flask(__name__).app_context():
        result = readiness.check_authentication_database_readiness()

    assert result.ready is False
    assert result.database_reachable is True
    assert result.missing_tables == ('external_identity_links', 'notifications')
    assert result.setup_required is True


def test_authentication_readiness_reports_database_outage(monkeypatch) -> None:
    def fail(_engine):
        raise SQLAlchemyError('offline')

    monkeypatch.setattr(readiness, 'inspect', fail)
    monkeypatch.setattr(readiness, 'db', SimpleNamespace(engine=object()))

    with Flask(__name__).app_context():
        result = readiness.check_authentication_database_readiness()

    assert result.ready is False
    assert result.database_reachable is False
    assert result.setup_required is False
