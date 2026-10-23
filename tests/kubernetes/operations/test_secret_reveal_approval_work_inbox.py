"""Protected Secret Reveal approval Work Inbox eligibility and composition tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.kubernetes.operations.secrets import approval_inbox

ROOT = Path(__file__).resolve().parents[3]


class Field:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return (self.name, 'eq', other)

    def __ne__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return (self.name, 'ne', other)

    def __gt__(self, other: object) -> tuple[str, str, object]:
        return (self.name, 'gt', other)

    def desc(self) -> str:
        return self.name + ':desc'


class Queue:
    def __init__(self, row: object) -> None:
        self.row = row
        self.conditions: tuple[object, ...] = ()
        self.order: tuple[object, ...] = ()
        self.limit_value = 0

    def filter(self, *conditions: object) -> 'Queue':
        self.conditions = conditions
        return self

    def count(self) -> int:
        return 1

    def order_by(self, *args: object) -> 'Queue':
        self.order = args
        return self

    def limit(self, value: int) -> 'Queue':
        self.limit_value = value
        return self

    def all(self) -> list[object]:
        return [self.row]


def _configure(monkeypatch, *, allowed: bool, active: bool = True, deleted: bool = False):
    record = SimpleNamespace(
        id='review-101',
        secret_name='safe-test-secret',
        namespace='testing',
        cluster=SimpleNamespace(name='Kubernetes Test'),
        requester=SimpleNamespace(display_label='Requester'),
        ticket_reference='INC-TEST-101',
        requested_at=datetime.now(UTC),
    )
    queue = Queue(record)
    fields = ['status', 'policy', 'expires_at', 'requester_user_id', 'requested_at', 'id']
    model = SimpleNamespace(query=queue, **{name: Field(name) for name in fields})

    viewer = SimpleNamespace(
        is_active=active,
        account_is_active=active,
        deleted_at=datetime.now(UTC) if deleted else None,
        has_permission=lambda key: allowed and key == 'kubernetes_secrets.approve_reveal',
    )

    class UserQuery:
        def filter_by(self, **kwargs):
            assert kwargs == {'id': 42}
            return self

        def first(self):
            return viewer

    monkeypatch.setattr(approval_inbox, 'User', SimpleNamespace(query=UserQuery()))
    monkeypatch.setattr(approval_inbox, 'SecretRevealRequest', model)
    monkeypatch.setattr(
        approval_inbox, 'url_for',
        lambda endpoint, **kwargs: '/secret-reveal/approvals?ticket=' + kwargs['pending_search'],
    )
    return queue


def test_eligible_approver_gets_committed_pending_request_not_secret_value(monkeypatch):
    queue = _configure(monkeypatch, allowed=True)
    result = approval_inbox.get_secret_reveal_approval_work_inbox(user_id=42)

    assert result['pending_count'] == result['total_count'] == 1
    assert len(result['items']) == 1
    assert result['items'][0]['request_id'] == 'review-101'
    assert result['items'][0]['is_pending'] is True
    assert result['items'][0]['action_url'].endswith('INC-TEST-101')
    assert 'secret_value' not in result['items'][0]
    assert 'key_name' not in result['items'][0]
    assert queue.limit_value == 8
    assert queue.order == ('requested_at:desc', 'id:desc')
    assert ('status', 'eq', 'pending') in queue.conditions
    assert ('policy', 'eq', 'approval_required') in queue.conditions
    assert ('requester_user_id', 'ne', 42) in queue.conditions
    expires = [c for c in queue.conditions if c[0] == 'expires_at']
    assert len(expires) == 1
    assert expires[0][1] == 'gt'
    assert abs((expires[0][2] - datetime.now(UTC)).total_seconds()) < 10


def test_ineligible_or_inactive_user_has_no_work_and_never_queries_requests(monkeypatch):
    for allowed, active, deleted in (
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ):
        queue = _configure(monkeypatch, allowed=allowed, active=active, deleted=deleted)
        assert approval_inbox.get_secret_reveal_approval_work_inbox(user_id=42) == {
            'items': [],
            'pending_count': 0,
            'total_count': 0,
        }
        assert queue.conditions == ()


def test_secret_reveal_inbox_uses_tenant_style_composition_and_shared_deck():
    queries = (ROOT / 'app/platform_operations/notifications/queries.py').read_text(encoding='utf-8')
    boot = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    panel_path = ROOT / 'app/templates/platform_operations/notifications/partials/_notification_deck_inbox.html'
    panel = panel_path.read_text(encoding='utf-8')
    source = (ROOT / 'app/kubernetes/operations/secrets/approval_inbox.py').read_text(encoding='utf-8')

    assert "app.extensions['kaori_secret_reveal_approval_work_inbox'] = get_secret_reveal_approval_work_inbox" in boot
    assert "current_app.extensions.get('kaori_secret_reveal_approval_work_inbox')" in queries
    assert 'secret_reveal_inbox = secret_inbox_provider(user_id=user_id)' in queries
    assert "secret_reveal_approval_inbox_items" in queries and panel
    assert "tenant_approval_inbox['pending_count']" in queries
    assert "secret_reveal_inbox['pending_count']" in queries
    assert "secret_reveal_requester_inbox['ready_count']" in queries
    assert 'Protected Secret Reveal approval requests' in panel
    assert 'Review in Protected Secret Reveal' in panel
    assert 'hx-boost="false"' in panel
    assert "kubernetes_secrets.approve_reveal" in source
    assert "SecretRevealRequest.status == 'pending'" in source
    assert "SecretRevealRequest.expires_at > datetime.now(UTC)" in source
    assert 'Secret value' not in panel
    assert 'from app.kubernetes.operations.secrets' not in queries



def test_requester_sees_only_committed_approved_unexpired_own_work(monkeypatch):
    queue = _configure(monkeypatch, allowed=True)
    record = queue.row
    record.approver = SimpleNamespace(display_label='Independent Reviewer')
    record.expires_at = datetime.now(UTC) + timedelta(minutes=5)
    record.decided_at = datetime.now(UTC)
    # Replace the role check with the requester-specific capability.
    viewer = SimpleNamespace(
        is_active=True,
        account_is_active=True,
        deleted_at=None,
        has_permission=lambda key: key == 'kubernetes_secrets.reveal',
    )

    class UserQuery:
        def filter_by(self, **kwargs):
            assert kwargs == {'id': 42}
            return self

        def first(self):
            return viewer

    monkeypatch.setattr(approval_inbox, 'User', SimpleNamespace(query=UserQuery()))
    monkeypatch.setattr(
        approval_inbox, 'url_for',
        lambda endpoint, **kw: '/reveal?reveal_view=' + kw['reveal_view'] + '&my_request_id=' + kw['my_request_id'],
    )
    queue_model = approval_inbox.SecretRevealRequest
    queue_model.decided_at = Field('decided_at')
    result = approval_inbox.get_secret_reveal_requester_work_inbox(user_id=42)

    assert result['ready_count'] == result['total_count'] == 1
    assert result['items'][0]['request_id'] == 'review-101'
    assert result['items'][0]['state'] == 'Ready to Reveal'
    assert result['items'][0]['approved_by'] == 'Independent Reviewer'
    assert result['items'][0]['action_url'].endswith('my_request_id=review-101')
    assert result['items'][0]['expires_at'] == record.expires_at
    assert 'secret_value' not in result['items'][0]
    assert 'key_name' not in result['items'][0]
    assert ('requester_user_id', 'eq', 42) in queue.conditions
    assert ('policy', 'eq', 'approval_required') in queue.conditions
    assert ('status', 'eq', 'approved') in queue.conditions
    assert len([c for c in queue.conditions if c[0] == 'expires_at' and c[1] == 'gt']) == 1
    assert queue.order == ('decided_at:desc', 'id:desc')
    assert queue.limit_value == 8


def test_requester_without_reveal_permission_or_active_account_has_no_inbox_work(monkeypatch):
    for allowed, active, deleted in (
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ):
        queue = _configure(monkeypatch, allowed=False)
        viewer = SimpleNamespace(
            is_active=active,
            account_is_active=active,
            deleted_at=datetime.now(UTC) if deleted else None,
            has_permission=lambda key: allowed and key == 'kubernetes_secrets.reveal',
        )

        class UserQuery:
            def filter_by(self, **kwargs):
                assert kwargs == {'id': 42}
                return self

            def first(self):
                return viewer

        monkeypatch.setattr(approval_inbox, 'User', SimpleNamespace(query=UserQuery()))
        assert approval_inbox.get_secret_reveal_requester_work_inbox(user_id=42) == {
            'items': [], 'ready_count': 0, 'total_count': 0,
        }
        assert queue.conditions == ()


def test_requester_work_inbox_uses_shared_notification_deck_and_no_reveal_mutation():
    boot = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    queries = (ROOT / 'app/platform_operations/notifications/queries.py').read_text(encoding='utf-8')
    panel = (
        ROOT / 'app/templates/platform_operations/notifications/partials/_notification_deck_inbox.html'
    ).read_text(encoding='utf-8')
    source = (ROOT / 'app/kubernetes/operations/secrets/approval_inbox.py').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/operations/secrets/reveal_routes.py').read_text(encoding='utf-8')

    assert "app.extensions['kaori_secret_reveal_requester_work_inbox'] = get_secret_reveal_requester_work_inbox" in boot
    assert "current_app.extensions.get('kaori_secret_reveal_requester_work_inbox')" in queries
    assert "secret_reveal_requester_inbox = requester_inbox_provider(user_id=user_id)" in queries
    assert "secret_reveal_requester_inbox['ready_count']" in queries
    assert "'secret_reveal_requester_inbox_items': secret_reveal_requester_inbox['items']" in queries
    assert "center.get('secret_reveal_requester_inbox_items', [])" in panel
    assert 'My approved Secret Reveal requests' in panel
    assert 'Ready to Reveal' in panel
    assert 'Open My Request' in panel
    assert 'hx-boost="false"' in panel
    assert "SecretRevealRequest.requester_user_id == user_id" in source
    assert "SecretRevealRequest.status == 'approved'" in source
    assert "SecretRevealRequest.policy == 'approval_required'" in source
    assert "viewer.has_permission('kubernetes_secrets.reveal')" in source
    assert 'my_request_id=record.id' in source
    assert 'Secret value' not in panel
    assert 'from app.kubernetes.operations.secrets' not in queries
    assert "@permission_required('kubernetes_secrets.reveal')" in routes
    assert "secret_reveal_requester_items" in panel.split('No assigned work', 1)[0]


def test_requester_active_work_requires_current_approved_owned_unexpired_state(monkeypatch):
    now = datetime.now(UTC)
    record = SimpleNamespace(
        id='review-101',
        secret_name='safe-test-secret',
        namespace='testing',
        cluster=SimpleNamespace(name='Kubernetes Test'),
        ticket_reference='INC-TEST-101',
        approver=None,
        decided_at=now,
        expires_at=now,
        requester_user_id=42,
        policy='approval_required',
        status='approved',
    )

    class ScopedQueue(Queue):
        def _matches(self):
            for field, operator, value in self.conditions:
                actual = getattr(self.row, field)
                if operator == 'eq' and actual != value:
                    return False
                if operator == 'gt' and not actual > value:
                    return False
            return True

        def count(self):
            return int(self._matches())

        def all(self):
            return [self.row] if self._matches() else []

    queue = ScopedQueue(record)
    names = ['requester_user_id', 'policy', 'status', 'expires_at', 'decided_at', 'id']
    monkeypatch.setattr(
        approval_inbox, 'SecretRevealRequest',
        SimpleNamespace(query=queue, **{key: Field(key) for key in names}),
    )
    viewer = SimpleNamespace(
        is_active=True,
        account_is_active=True,
        deleted_at=None,
        has_permission=lambda capability: capability == 'kubernetes_secrets.reveal',
    )

    class UserQuery:
        def filter_by(self, **kwargs):
            assert kwargs == {'id': 42}
            return self

        def first(self):
            return viewer

    monkeypatch.setattr(approval_inbox, 'User', SimpleNamespace(query=UserQuery()))
    monkeypatch.setattr(
        approval_inbox, 'url_for',
        lambda endpoint, **kw: '/reveal?my_request_id=' + kw['my_request_id'],
    )

    # A committed status/expiry/ownership transition immediately removes the work item.
    for status, owner, policy, expiry_delta_seconds, expected in (
        ('approved', 42, 'approval_required', -60, 1),
        ('pending', 42, 'approval_required', -60, 0),
        ('denied', 42, 'approval_required', -60, 0),
        ('revealed', 42, 'approval_required', -60, 0),
        ('expired', 42, 'approval_required', -60, 0),
        ('approved', 7, 'approval_required', -60, 0),
        ('approved', 42, 'step_up', -60, 0),
        ('approved', 42, 'approval_required', 60, 0),
    ):
        record.status = status
        record.requester_user_id = owner
        record.policy = policy
        record.expires_at = now - timedelta(seconds=seconds_ago)
        result = approval_inbox.get_secret_reveal_requester_work_inbox(user_id=42)
        assert result['ready_count'] == expected
        assert len(result['items']) == expected


def test_secret_reveal_effective_status_preserves_read_only_expiry() -> None:
    from app.models.secret_reveal import SecretRevealRequest

    record = SecretRevealRequest()
    record.status = 'approved'
    record.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    assert record.effective_status == 'expired'
    assert record.status == 'approved'  # no mutation on read
    record.expires_at = datetime.now(UTC) + timedelta(minutes=5)
    assert record.effective_status == 'approved'
    record.status = 'revealed'
    record.expires_at = datetime.now(UTC) - timedelta(hours=1)
    assert record.effective_status == 'revealed'
    record.status = 'pending'
    record.expires_at = (datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None)
    assert record.effective_status == 'expired'  # SQLite naive datetime
