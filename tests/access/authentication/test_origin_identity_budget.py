"""AL-05C opt-in uniform origin/identity budget; no recovery-account oracle."""

from unittest.mock import MagicMock, Mock

import pytest
from flask import Flask
from redis.exceptions import RedisError

from app.access.authentication import login_protection as protection
from app.access.authentication.lockout_policy import LockoutMode
from app.access.authentication.login_protection import LoginProtectionUnavailable

SECRET = 'fixture-only-shared-key-not-production'


def test_origin_pair_normalization_namespace_and_privacy() -> None:
    key = protection.origin_identity_bucket('  ExampleUser  ', '192.0.2.1', SECRET)
    assert key == protection.origin_identity_bucket('exampleuser', '::ffff:192.0.2.1', SECRET)
    assert protection.origin_identity_bucket('exampleuser', '2001:db8::1', SECRET) == (
        protection.origin_identity_bucket('exampleuser', '2001:0db8:0:0:0:0:0:1', SECRET)
    )
    assert key.split(':')[1] != protection.identity_bucket('exampleuser', SECRET).split(':')[1]
    assert key != protection.origin_identity_bucket('exampleuser', '192.0.2.1', SECRET + '-rotated')
    assert all(value not in key for value in ('exampleuser', '192.0.2.1', SECRET))
    assert 0 <= int(key.rsplit(':', 1)[1], 16) < protection.BUCKET_COUNT


@pytest.mark.parametrize('origin', (None, '', 'invalid', '192.0.2.1, 192.0.2.2', 'fe80::1%eth0'))
def test_invalid_origin_denied(origin: str | None) -> None:
    with pytest.raises(LoginProtectionUnavailable):
        protection.origin_identity_bucket('fixture', origin, SECRET)


@pytest.mark.parametrize('mode', tuple(LockoutMode))
@pytest.mark.parametrize('enabled', (False, True))
def test_optional_uniform_budget_is_mode_scoped(
    monkeypatch: pytest.MonkeyPatch, mode: LockoutMode, enabled: bool
) -> None:
    app = Flask(__name__)
    app.config['AUTH_LOGIN_ORIGIN_BUDGET_ENABLED'] = enabled
    monkeypatch.setattr(protection, 'read_login_policy', lambda: (mode, 2))
    identity = Mock(return_value=False)
    origin = Mock(return_value=True)
    monkeypatch.setattr(protection, 'shared_identity_budget', identity)
    monkeypatch.setattr(protection, 'shared_origin_identity_budget', origin)
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '192.0.2.1'},
                                  headers={'X-Forwarded-For': '192.0.2.99'}):
        result = protection.check_login_request('fixture')
    applicable = enabled and mode != LockoutMode.DISABLED
    assert result.origin_over_budget == applicable
    assert result.over_budget == applicable
    assert result.blocked == (applicable and mode == LockoutMode.ENFORCED)
    assert identity.call_count == int(mode != LockoutMode.DISABLED)
    if applicable:
        origin.assert_called_once_with('fixture', '192.0.2.1')
    else:
        origin.assert_not_called()


def test_pair_budget_and_probe_share_bounded_redis_script(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.config.update(SECRET_KEY=SECRET, RATELIMIT_ENABLED=True, RATELIMIT_STORAGE_URI='redis://localhost:6379/0',
                      AUTH_LOGIN_ORIGIN_BUDGET_ENABLED=True)
    client = Mock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(protection.Redis, 'from_url', factory)
    with app.app_context():
        client.eval.return_value = 3
        assert not protection.shared_origin_identity_budget('fixture', '192.0.2.1')
        client.eval.return_value = 4
        assert protection.shared_origin_identity_budget('fixture', '192.0.2.1')
        assert client.eval.call_args.args[-2:] == (60, 3)
        client.eval.return_value = 5
        with pytest.raises(LoginProtectionUnavailable):
            protection.shared_origin_identity_budget('fixture', '192.0.2.1')
        client.eval.reset_mock()
        client.eval.return_value = 1
        protection.probe_shared_login_protection()
        assert [call.args[-2:] for call in client.eval.call_args_list] == [(60, 30), (60, 3)]
        assert all(call.args[2].endswith(':qualification-probe') for call in client.eval.call_args_list)
        client.eval.side_effect = RedisError('fixture')
        with pytest.raises(LoginProtectionUnavailable):
            protection.shared_origin_identity_budget('fixture', '192.0.2.1')
