from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from app.auth import audit


class NotificationStub:
    pass


def _app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    return app


def test_authentication_activity_records_safe_provider_and_request_context(monkeypatch) -> None:
    added: list[NotificationStub] = []
    commits: list[bool] = []
    monkeypatch.setattr(audit, 'Notification', NotificationStub)
    monkeypatch.setattr(
        audit,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                add=lambda item: added.append(item),
                commit=lambda: commits.append(True),
                rollback=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(
        audit,
        'parse_user_agent',
        lambda _value: {'browser': 'Firefox', 'os': 'Windows', 'device': 'Desktop'},
    )
    user = SimpleNamespace(
        id=7,
        display_label='KAORI Operator',
        email='operator@example.com',
        role_display_name='Operator',
    )

    with _app().test_request_context(
        '/auth/login',
        headers={'User-Agent': 'test-agent'},
        environ_base={'REMOTE_ADDR': '10.0.0.9'},
    ):
        audit.record_authentication_activity(
            action='login',
            username='operator',
            source='google_oidc',
            result='success',
            reason='success',
            user=user,
        )

    assert commits == [True]
    assert len(added) == 1
    event = added[0]
    assert event.event_type == 'authentication'
    assert event.status == 'success'
    assert event.metadata_json['authentication_provider'] == 'Google OpenID Connect'
    assert event.metadata_json['ip_address'] == '10.0.0.9'
    assert event.metadata_json['browser'] == 'Firefox'
    assert 'password' not in event.metadata_json
    assert 'token' not in event.metadata_json


def test_authentication_audit_failure_is_non_blocking_and_rolls_back(monkeypatch) -> None:
    rollbacks: list[bool] = []
    monkeypatch.setattr(audit, 'Notification', NotificationStub)

    def fail_commit() -> None:
        raise RuntimeError('audit storage unavailable')

    monkeypatch.setattr(
        audit,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                add=lambda _item: None,
                commit=fail_commit,
                rollback=lambda: rollbacks.append(True),
            )
        ),
    )
    monkeypatch.setattr(
        audit,
        'parse_user_agent',
        lambda _value: {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'},
    )

    with _app().test_request_context('/auth/login'):
        audit.record_authentication_activity(
            action='login',
            username='operator',
            source='database',
            result='failed',
            reason='invalid_credentials',
        )

    assert rollbacks == [True]
