"""Bounded committed authentication abuse observation (#5420).

Observe only. This is not a password-verification counter, a SIEM, or an
AlertCase lifecycle. No raw user/source identifiers are persisted here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Any

from flask import current_app
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert

from app.extensions.db import db
from app.models.alert_signal import AlertSignalSnapshot
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import system_actor_snapshot
from app.platform_operations.notifications.writer import NotificationPersistenceEvidence, persist_notification

DOMAIN = 'authentication'
ASSET_KEY = 'local-deployment'
SIGNAL_KEY = 'authentication.login_abuse'
WINDOW_MINUTES = 15
SETTLE_MINUTES = 2
MAX_ROWS = 2000
MAX_RECIPIENTS = 10
# Initial observation thresholds, not enforcement rules or confirmed incidents.
REJECTION_THRESHOLD = 30
TARGET_THRESHOLD = 5
SOURCE_THRESHOLD = 5
RECOVERY_THRESHOLD = 5
BUDGET_THRESHOLD = 10


def closed_window(now: datetime) -> tuple[datetime, datetime]:
    """Use the latest settled, non-overlapping UTC window; no unbounded catch-up."""
    settled = now - timedelta(minutes=SETTLE_MINUTES)
    seconds = WINDOW_MINUTES * 60
    end = datetime.fromtimestamp(int(settled.timestamp()) // seconds * seconds, UTC)
    return end - timedelta(minutes=WINDOW_MINUTES), end


def summarize_abuse(
    rows: Iterable[tuple[dict[str, Any] | None, int | None, bool | None]],
) -> dict[str, Any]:
    """Use audit actions, never count two different producers as one password total."""
    counts: Counter[str] = Counter()
    targets: set[int] = set()
    sources: set[str] = set()
    target_counts: Counter[int] = Counter()
    recovery_counts: Counter[int] = Counter()
    sample_rows = 0
    truncated = False
    for metadata, target, recovery_principal in rows:
        if sample_rows == MAX_ROWS:
            truncated = True
            break
        sample_rows += 1
        if not isinstance(metadata, dict):
            continue
        schema = metadata.get('audit_schema')
        action = metadata.get('access_action')
        if schema == 'authentication.v2' and action == 'login' and metadata.get('result') == 'failed':
            reason = metadata.get('reason_code')
            if reason == 'invalid_credentials':
                counts['credential_rejections'] += 1
                if target is not None:
                    targets.add(target)
                    target_counts[target] += 1
                    if recovery_principal is True and metadata.get('auth_source') == 'database':
                        recovery_counts[target] += 1
                try:
                    source = metadata.get('ip_address')
                    if isinstance(source, str):
                        sources.add(str(ip_address(source)))
                except ValueError:
                    pass
            elif reason == 'rate_limited':
                counts['endpoint_rate_limited'] += 1
            elif reason == 'bot_challenge_failed':
                counts['challenge_rejections'] += 1
        elif schema == 'authentication.security.v1':
            if action == 'identity_budget_exceeded':
                counts['identity_budget_observations'] += 1
            elif action == 'lockout_threshold_reached':
                if metadata.get('policy_mode') == 'enforced':
                    counts['enforced_lock_transitions'] += 1
                elif metadata.get('policy_mode') == 'monitor_only':
                    counts['monitor_threshold_observations'] += 1
    peak_target = max(target_counts.values(), default=0)
    peak_recovery = max(recovery_counts.values(), default=0)
    indicators: list[str] = []
    if counts['credential_rejections'] >= REJECTION_THRESHOLD:
        indicators.append('elevated_credential_rejections')
    if counts['credential_rejections'] >= REJECTION_THRESHOLD and len(targets) >= TARGET_THRESHOLD:
        indicators.append('multi_target_rejection_pattern')
    if counts['credential_rejections'] >= REJECTION_THRESHOLD and len(sources) >= SOURCE_THRESHOLD:
        indicators.append('multi_source_rejection_pattern')
    if peak_recovery >= RECOVERY_THRESHOLD:
        indicators.append('recovery_principal_rejection_pattern')
    if counts['identity_budget_observations'] >= BUDGET_THRESHOLD:
        indicators.append('shared_budget_pressure')
    if counts['enforced_lock_transitions']:
        indicators.append('enforced_lock_transition')
    if truncated:
        indicators.append('sample_capacity_exceeded')
    return {
        'schema_version': 1,
        'coverage': 'partial' if truncated else 'bounded_window',
        'sample_rows': sample_rows,
        'credential_rejections': counts['credential_rejections'],
        'known_targets': len(targets),
        'distinct_observed_sources': len(sources),
        'peak_known_target_rejections': peak_target,
        'peak_current_recovery_principal_rejections': peak_recovery,
        'endpoint_rate_limited': counts['endpoint_rate_limited'],
        'challenge_rejections': counts['challenge_rejections'],
        'identity_budget_observations': counts['identity_budget_observations'],
        'enforced_lock_transitions': counts['enforced_lock_transitions'],
        'monitor_threshold_observations': counts['monitor_threshold_observations'],
        'indicators': indicators,
    }


def _snapshot_locked() -> AlertSignalSnapshot:
    """PostgreSQL uniqueness and row lock fence concurrent workers and retries."""
    db.session.execute(
        insert(AlertSignalSnapshot).values(
            domain=DOMAIN, asset_key=ASSET_KEY, signal_key=SIGNAL_KEY, status='failed',
        ).on_conflict_do_nothing(index_elements=['domain', 'asset_key', 'signal_key'])
    )
    return db.session.execute(
        select(AlertSignalSnapshot).where(
            AlertSignalSnapshot.domain == DOMAIN,
            AlertSignalSnapshot.asset_key == ASSET_KEY,
            AlertSignalSnapshot.signal_key == SIGNAL_KEY,
        ).with_for_update().execution_options(populate_existing=True)
    ).scalar_one()


def _stage_notifications(payload: dict[str, Any], recipients: list[int]) -> None:
    """One audit row and at most MAX_RECIPIENTS personal deck rows per window."""
    evidence = NotificationPersistenceEvidence(metadata=payload, actor=system_actor_snapshot())
    for user_id in [None, *recipients]:
        persist_notification(
            user_id=user_id, event_type='authentication', status='warning',
            title='Login Abuse Observation',
            message='Committed authentication evidence contains indicators requiring review.',
            detail='Aggregate observation only; no confirmed attack or individual attribution is asserted.',
            evidence=evidence, deck_visible=user_id is not None, commit=False,
        )


def refresh_authentication_abuse_signal() -> dict[str, Any]:
    """Commit one bounded aggregate and optional notifications, or roll back all."""
    if not current_app.config.get('AUTH_ABUSE_SIGNAL_ENABLED'):
        return {'state': 'disabled'}
    try:
        if db.session.get_bind().dialect.name != 'postgresql':
            raise RuntimeError('Authentication abuse observation requires PostgreSQL.')
        now = db.session.execute(select(func.clock_timestamp())).scalar_one()
        start, end = closed_window(now)
        snapshot = _snapshot_locked()
        previous = snapshot.generated_at
        if previous is not None and previous >= end:
            db.session.rollback()
            return {'state': 'already_evaluated'}
        # Only materialize a bounded page from the existing time/event indexes.
        # Current recovery-principal classification is not historical proof.
        current_recovery = and_(
            User.is_super_admin.is_(True), User.auth_source == 'database',
            User.account_is_active.is_(True), User.deleted_at.is_(None),
        )
        rows = db.session.execute(
            select(Notification.metadata_json, Notification.user_id, current_recovery)
            .outerjoin(User, User.id == Notification.user_id)
            .where(
                Notification.event_type == 'authentication',
                Notification.actor_key == 'unauthenticated',
                Notification.created_at >= start, Notification.created_at < end,
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(MAX_ROWS + 1)
        ).tuples().all()
        payload = summarize_abuse(rows)
        payload.update({
            'audit_schema': 'authentication.security.v1',
            'access_action': 'lockout_abuse_observation',
            'window_start': start.isoformat(),
            'window_end': end.isoformat(),
            'missed_prior_window': previous is not None and previous < start,
            'source_authority': 'committed_activity_audit',
        })
        if payload['missed_prior_window']:
            payload['coverage'] = 'partial'
            payload['indicators'].append('observation_window_gap')
        if payload['indicators']:
            recipient_rows = db.session.execute(
                select(User.id).where(current_recovery).order_by(User.id).limit(MAX_RECIPIENTS + 1)
            ).scalars().all()
            recipients = list(recipient_rows[:MAX_RECIPIENTS])
            payload['recipient_limit_reached'] = len(recipient_rows) > MAX_RECIPIENTS
            payload['recipient_count'] = len(recipients)
            _stage_notifications(payload, recipients)
        snapshot.status = 'ready'
        snapshot.payload_json = payload
        snapshot.generated_at = end
        snapshot.expires_at = end + timedelta(minutes=WINDOW_MINUTES + SETTLE_MINUTES + 5)
        snapshot.last_attempt_at = now
        snapshot.last_error = None
        db.session.commit()
        return {'state': 'observed', 'coverage': payload['coverage'], 'indicators': len(payload['indicators'])}
    except Exception:
        db.session.rollback()
        raise


def read_authentication_abuse_signal() -> dict[str, Any]:
    """Committed-only read contract for a future qualified recommendation rule."""
    if not current_app.config.get('AUTH_ABUSE_SIGNAL_ENABLED'):
        return {'state': 'disabled', 'payload': None}
    snapshot = db.session.execute(
        select(AlertSignalSnapshot).where(
            AlertSignalSnapshot.domain == DOMAIN,
            AlertSignalSnapshot.asset_key == ASSET_KEY,
            AlertSignalSnapshot.signal_key == SIGNAL_KEY,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        return {'state': 'missing', 'payload': None}
    if snapshot.status != 'ready' or snapshot.payload_json is None or snapshot.expires_at is None:
        return {'state': 'unavailable', 'payload': None}
    expires = snapshot.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if datetime.now(UTC) >= expires:
        return {'state': 'stale', 'payload': None}
    payload = dict(snapshot.payload_json)
    if payload.get('schema_version') != 1 or payload.get('coverage') not in ('bounded_window', 'partial'):
        return {'state': 'unavailable', 'payload': None}
    return {'state': 'partial' if payload['coverage'] == 'partial' else 'fresh', 'payload': payload}
