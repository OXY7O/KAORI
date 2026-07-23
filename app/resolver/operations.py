from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceExecutionJournal
from app.models.resolver import ResolverOperationalControl


class ResolverOperationalError(RuntimeError):
    """Raised when an operational safety control blocks resolver execution."""


@dataclass(frozen=True, slots=True)
class ResolverReadiness:
    ready: bool
    reasons: tuple[str, ...]
    global_enabled: bool
    cluster_enabled: bool
    circuit_open: bool
    active_executions: int
    concurrency_limit: int


def get_or_create_control(*, cluster_id: str | None, actor_user_id: int | None = None) -> ResolverOperationalControl:
    record = ResolverOperationalControl.query.filter_by(cluster_id=cluster_id).one_or_none()
    if record is None:
        record = ResolverOperationalControl()
        record.cluster_id = cluster_id
        record.updated_by_user_id = actor_user_id
        db.session.add(record)
        db.session.flush()
    return record


def update_control(
    *,
    cluster_id: str | None,
    global_kill_switch: bool | None = None,
    maintenance_mode: bool | None = None,
    concurrency_limit: int | None = None,
    rate_limit_per_minute: int | None = None,
    circuit_failure_threshold: int | None = None,
    circuit_cooldown_seconds: int | None = None,
    actor_user_id: int | None,
) -> ResolverOperationalControl:
    record = get_or_create_control(cluster_id=cluster_id, actor_user_id=actor_user_id)
    if global_kill_switch is not None:
        if cluster_id is not None:
            raise ResolverOperationalError('Global kill switch may only be changed on the global control record.')
        record.global_kill_switch = bool(global_kill_switch)
    if maintenance_mode is not None:
        record.maintenance_mode = bool(maintenance_mode)
    if concurrency_limit is not None:
        record.concurrency_limit = max(1, int(concurrency_limit))
    if rate_limit_per_minute is not None:
        record.rate_limit_per_minute = max(1, int(rate_limit_per_minute))
    if circuit_failure_threshold is not None:
        record.circuit_failure_threshold = max(1, int(circuit_failure_threshold))
    if circuit_cooldown_seconds is not None:
        record.circuit_cooldown_seconds = max(1, int(circuit_cooldown_seconds))
    record.updated_by_user_id = actor_user_id
    _audit_control(record, actor_user_id)
    db.session.flush()
    return record


def assert_execution_allowed(journal: IntelligenceExecutionJournal, *, now: datetime | None = None) -> ResolverReadiness:
    current = now or datetime.now(UTC)
    cluster_id = journal.decision.cluster_id
    global_control = ResolverOperationalControl.query.filter_by(cluster_id=None).one_or_none()
    cluster_control = ResolverOperationalControl.query.filter_by(cluster_id=cluster_id).one_or_none()
    reasons: list[str] = []
    global_enabled = not bool(global_control and global_control.global_kill_switch)
    cluster_enabled = not bool(cluster_control and cluster_control.maintenance_mode)
    if not global_enabled:
        reasons.append('Global resolver kill switch is active.')
    if not cluster_enabled:
        reasons.append('Resolver maintenance mode is active for this cluster.')
    control = cluster_control or global_control
    concurrency_limit = control.concurrency_limit if control else 1
    active = IntelligenceExecutionJournal.query.join(IntelligenceExecutionJournal.decision).filter(
        IntelligenceExecutionJournal.orchestration_status == 'running',
        IntelligenceExecutionJournal.id != journal.id,
        IntelligenceExecutionJournal.decision.has(cluster_id=cluster_id),
    ).count()
    if active >= concurrency_limit:
        reasons.append('Resolver concurrency limit has been reached for this cluster.')
    circuit_open = bool(control and control.circuit_open_until and _aware(control.circuit_open_until) > current)
    if circuit_open:
        reasons.append('Resolver circuit breaker is open for this cluster.')
    if control:
        since = current - timedelta(minutes=1)
        recent = IntelligenceExecutionJournal.query.filter(
            IntelligenceExecutionJournal.id != journal.id,
            IntelligenceExecutionJournal.created_at >= since,
            IntelligenceExecutionJournal.decision.has(cluster_id=cluster_id),
        ).count()
        if recent >= control.rate_limit_per_minute:
            reasons.append('Resolver rate limit has been reached for this cluster.')
    readiness = ResolverReadiness(
        ready=not reasons,
        reasons=tuple(reasons),
        global_enabled=global_enabled,
        cluster_enabled=cluster_enabled,
        circuit_open=circuit_open,
        active_executions=active,
        concurrency_limit=concurrency_limit,
    )
    if not readiness.ready:
        raise ResolverOperationalError(' '.join(readiness.reasons))
    return readiness


def record_operational_failure(journal: IntelligenceExecutionJournal, *, now: datetime | None = None) -> None:
    current = now or datetime.now(UTC)
    control = get_or_create_control(cluster_id=journal.decision.cluster_id)
    control.consecutive_failures += 1
    if control.consecutive_failures >= control.circuit_failure_threshold:
        open_until = current + timedelta(seconds=control.circuit_cooldown_seconds)
        control.circuit_open_until = open_until
        _audit_journal(journal, 'resolver.circuit.opened', {
            'consecutive_failures': control.consecutive_failures,
            'open_until': open_until.isoformat(),
        })
    db.session.flush()


def record_operational_success(journal: IntelligenceExecutionJournal) -> None:
    control = ResolverOperationalControl.query.filter_by(cluster_id=journal.decision.cluster_id).one_or_none()
    if control is None:
        return
    control.consecutive_failures = 0
    control.circuit_open_until = None
    db.session.flush()


def resolver_metrics_snapshot(*, now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(UTC)
    stale_before = current - timedelta(minutes=10)
    statuses: dict[str, int] = {}
    status_rows = (
        db.session.query(IntelligenceExecutionJournal.orchestration_status, func.count(IntelligenceExecutionJournal.id))
        .group_by(IntelligenceExecutionJournal.orchestration_status)
        .all()
    )
    for status, count in status_rows:
        if status is not None:
            statuses[str(status)] = _count(count)
    return {
        'queued': _count(statuses.get('queued')),
        'running': _count(statuses.get('running')),
        'retry_wait': _count(statuses.get('retry_wait')),
        'dead_letter': _count(statuses.get('dead_letter')),
        'stuck_running': IntelligenceExecutionJournal.query.filter(
            IntelligenceExecutionJournal.orchestration_status == 'running',
            IntelligenceExecutionJournal.last_heartbeat_at < stale_before,
        ).count(),
    }


def requeue_dead_letter(journal: IntelligenceExecutionJournal, *, actor_user_id: int | None) -> None:
    if journal.orchestration_status != 'dead_letter':
        raise ResolverOperationalError('Only dead-letter execution journals may be requeued.')
    journal.orchestration_status = 'retry_wait'
    journal.next_retry_at = datetime.now(UTC)
    journal.completed_at = None
    journal.last_error_code = None
    journal.error_message = None
    _audit_journal(journal, 'resolver.dead_letter.requeued', {'actor_user_id': actor_user_id})
    db.session.flush()


def _audit_control(record: ResolverOperationalControl, actor_user_id: int | None) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'resolver_operational_control'
    event.target_id = str(record.cluster_id or 'global')
    event.action = 'resolver.operational_control.updated'
    event.summary = 'KAORI resolver operational control updated.'
    event.metadata_json = {
        'global_kill_switch': record.global_kill_switch,
        'maintenance_mode': record.maintenance_mode,
        'concurrency_limit': record.concurrency_limit,
        'rate_limit_per_minute': record.rate_limit_per_minute,
    }
    db.session.add(event)


def _audit_journal(journal: IntelligenceExecutionJournal, action: str, metadata: dict[str, object]) -> None:
    event = AuditEvent()
    event.actor_user_id = journal.requested_by_user_id
    event.target_type = 'intelligence_execution_journal'
    event.target_id = journal.public_id
    event.action = action
    event.summary = action
    event.metadata_json = metadata
    db.session.add(event)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _count(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
