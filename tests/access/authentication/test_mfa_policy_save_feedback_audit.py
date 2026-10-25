"""MFA policy Save has durable toast and truthful committed Activity Audit (#3208)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask, session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.access import authentication_security as security_routes
from app.platform_operations.notifications.event_catalog import build_event_context
from app.platform_operations.notifications.feedback import pop_operational_feedback


class PolicyStore:
    def __init__(self, *, mode: str = 'disabled', fail_commit: bool = False) -> None:
        self.policy = SimpleNamespace(mfa_mode=mode)
        self.original_mode = mode
        self.fail_commit = fail_commit
        self.executions: list[object] = []
        self.staged: list[object] = []
        self.committed: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model: object, identifier: int, *, with_for_update: bool = False) -> object:
        assert model is security_routes.AuthenticationSecurityPolicy
        assert identifier == 1 and with_for_update
        return self.policy

    def execute(self, statement: object) -> None:
        self.executions.append(statement)

    def add(self, item: object) -> None:
        self.staged.append(item)

    def commit(self) -> None:
        if self.fail_commit:
            raise SQLAlchemyError('simulated persistence outage')
        self.commits += 1
        self.committed.extend(self.staged)
        self.staged.clear()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.policy.mfa_mode = self.original_mode
        self.staged.clear()


def _app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'mfa-policy-feedback-only-test'
    access = Blueprint('access', __name__, url_prefix='/access')
    access.register_blueprint(security_routes.bp, url_prefix='/authentication-security')
    app.register_blueprint(access)
    auth = Blueprint('auth', __name__, url_prefix='/auth')

    @auth.get('/login')
    def login() -> str:
        return 'Sign in'

    app.register_blueprint(auth)
    return app


def _install_stubs(monkeypatch: pytest.MonkeyPatch, store: PolicyStore) -> list[dict[str, object]]:
    actor = SimpleNamespace(id=27)
    evidence: list[dict[str, object]] = []

    def stage(_actor: object, **kwargs: object) -> dict[str, object]:
        assert _actor is actor
        evidence.append(kwargs)
        return kwargs

    monkeypatch.setattr(security_routes, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(security_routes, 'current_user', SimpleNamespace(_get_current_object=lambda: actor))
    monkeypatch.setattr(security_routes, 'validate_csrf', lambda _value: None)
    monkeypatch.setattr(security_routes, 'stage_authentication_security_event', stage)

    def logout() -> None:
        session.pop('_user_id', None)
        session['_remember'] = 'clear'

    monkeypatch.setattr(security_routes, 'logout_user', logout)
    return evidence


def _submit(app: Flask, mode: str):
    return app.test_request_context(
        '/access/authentication-security/mfa/policy',
        method='POST',
        data={'csrf_token': 'test', 'mfa_mode': mode, 'acknowledge_policy_impact': 'yes'},
    )


def test_changed_policy_audit_commits_before_session_clear_and_toast_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PolicyStore()
    audit = _install_stubs(monkeypatch, store)
    with _submit(_app(), 'optional'):
        session['_user_id'] = '27:1'
        session['auth_session_ref'] = 'no-leak-session-reference'
        response = security_routes.save_mfa_policy.__wrapped__()

        assert response.status_code == 302
        assert response.location.endswith('/auth/login')
        assert '_user_id' not in session
        assert 'auth_session_ref' not in session
        assert session['_remember'] == 'clear'
        result = pop_operational_feedback()
        assert result is not None
        assert result['status'] == 'success'
        assert result['activity_audit_saved'] is False  # Toast is not a second audit write.
        assert result['title'] == 'MFA policy updated'
        assert 'sign in again' in result['message']
        assert 'no-leak-session-reference' not in str(result)

    assert store.policy.mfa_mode == 'optional'
    assert store.commits == 1
    assert len(store.executions) == 1
    assert len(store.committed) == 1
    assert audit == [
        {
            'action': 'mfa_policy_changed',
            'authenticated': True,
            'success': True,
            'previous_mode': 'disabled',
            'next_mode': 'optional',
        }
    ]


def test_unchanged_policy_is_audited_without_fake_transition_or_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PolicyStore()
    audit = _install_stubs(monkeypatch, store)
    with _submit(_app(), 'disabled'):
        session['_user_id'] = '27:1'
        response = security_routes.save_mfa_policy.__wrapped__()
        assert response.status_code == 302
        assert 'tab=mfa' in response.location
        assert session['_user_id'] == '27:1'
        result = pop_operational_feedback()
        assert result is not None
        assert result['status'] == 'info'
        assert result['title'] == 'MFA policy unchanged'
        assert 'no sessions were revoked' in result['message']

    assert store.commits == 1 and not store.executions
    assert len(store.committed) == 1
    assert audit[0]['action'] == 'mfa_policy_unchanged'
    assert audit[0]['previous_mode'] == audit[0]['next_mode'] == 'disabled'


def test_failed_commit_rolls_back_and_never_emits_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PolicyStore(fail_commit=True)
    _install_stubs(monkeypatch, store)
    with _submit(_app(), 'optional'):
        session['_user_id'] = '27:1'
        with pytest.raises(HTTPException) as error:
            security_routes.save_mfa_policy.__wrapped__()
        assert error.value.code == 503
        assert session['_user_id'] == '27:1'
        result = pop_operational_feedback()
        assert result is not None
        assert result['status'] == 'error'
        assert result['title'] == 'MFA policy not saved'

    assert store.policy.mfa_mode == 'disabled'
    assert store.rollbacks == 1 and store.commits == 0
    assert not store.committed


@pytest.mark.parametrize(
    ('access_action', 'target_name', 'action_label'),
    [
        ('mfa_policy_changed', 'MFA Policy', 'MFA Policy Changed'),
        ('mfa_policy_unchanged', 'MFA Policy', 'MFA Policy Unchanged'),
        ('mfa_enrollment_confirmed', 'MFA Factor', 'MFA Enrollment Confirmed'),
        ('bot_policy_changed', 'Bot Protection', 'Bot Policy Changed'),
    ],
)
def test_security_control_events_are_not_mislabeled_as_login(
    access_action: str, target_name: str, action_label: str
) -> None:
    context = build_event_context(
        'authentication',
        {'access_action': access_action, 'result': 'success'},
        action_label,
    )
    assert context['module_label'] == 'Access'
    assert context['target_type'] == 'Security Control'
    assert context['target_name'] == target_name
    assert context['source_label'] == 'Authentication security'
    assert next(value['value'] for value in context['context_items'] if value['label'] == 'Action') == action_label


def test_normal_login_audit_still_describes_a_user_session() -> None:
    context = build_event_context(
        'authentication',
        {'access_action': 'login', 'result': 'success', 'username': 'local-test'},
        'User Signed In',
    )
    assert context['target_type'] == 'User Session'
    assert context['target_name'] == 'local-test'
    assert context['source_label'] == 'Authentication provider'
    assert next(value['value'] for value in context['context_items'] if value['label'] == 'Action') == 'Sign in'
