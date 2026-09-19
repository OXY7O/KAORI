from __future__ import annotations

from datetime import datetime
from typing import Any

OPERATIONAL_STATE_TONES = {
    'Ready': 'normal',
    'Starting': 'pending',
    'Not Ready': 'warning',
    'Terminating': 'warning',
    'Failed': 'critical',
    'Completed': 'info',
    'Unknown': 'unknown',
}

CRITICAL_WAITING_REASONS = {
    'crashloopbackoff',
    'containercannotrun',
    'createcontainerconfigerror',
    'createcontainererror',
    'errimagepull',
    'imagepullbackoff',
    'invalidimagename',
    'runcontainererror',
}


def pod_ready_values(value: str | None) -> tuple[int, int] | None:
    if not value or '/' not in value:
        return None
    ready, total = value.split('/', maxsplit=1)
    try:
        return int(ready), int(total)
    except (TypeError, ValueError):
        return None


def pod_operational_state(phase: str | None, ready: str | None) -> tuple[str, str, str]:
    phase_label = str(phase or 'Unknown')
    normalized_phase = phase_label.casefold()
    ready_values = pod_ready_values(ready)

    if normalized_phase == 'terminating':
        state = 'Terminating'
    elif normalized_phase == 'failed':
        state = 'Failed'
    elif normalized_phase == 'pending':
        state = 'Starting'
    elif normalized_phase == 'succeeded':
        state = 'Completed'
    elif normalized_phase == 'running' and ready_values:
        ready_count, ready_total = ready_values
        state = 'Ready' if ready_total > 0 and ready_count == ready_total else 'Not Ready'
    else:
        state = 'Unknown'

    evidence = phase_label
    if ready_values:
        evidence = f'{phase_label} · {ready_values[0]}/{ready_values[1]} Ready'
    elif str(ready or '').casefold() == 'not reported':
        evidence = f'{phase_label} · Container readiness not reported'
    return state, OPERATIONAL_STATE_TONES[state], evidence


def parse_inventory_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def condition_presentation(condition: dict[str, Any]) -> dict[str, Any]:
    condition_type = str(condition.get('type') or 'Unknown')
    status = str(condition.get('status') or 'Unknown')
    reason = str(condition.get('reason') or '').strip() or None
    normalized_type = condition_type.casefold()
    normalized_status = status.casefold()

    if normalized_type in {'ready', 'containersready'}:
        label = 'Ready' if normalized_status == 'true' else ('Not Ready' if normalized_status == 'false' else 'Unknown')
        tone = 'normal' if normalized_status == 'true' else ('warning' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'podscheduled':
        label = (
            'Scheduled' if normalized_status == 'true' else ('Pending' if normalized_status == 'false' else 'Unknown')
        )
        tone = 'normal' if normalized_status == 'true' else ('pending' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'podreadytostartcontainers':
        label = (
            'Runtime Sandbox Ready'
            if normalized_status == 'true'
            else ('Runtime Sandbox Pending' if normalized_status == 'false' else 'Unknown')
        )
        tone = 'normal' if normalized_status == 'true' else ('pending' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'initialized':
        label = (
            'Initialized'
            if normalized_status == 'true'
            else ('Starting' if normalized_status == 'false' else 'Unknown')
        )
        tone = 'normal' if normalized_status == 'true' else ('pending' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'disruptiontarget':
        label = (
            'Disruption Target'
            if normalized_status == 'true'
            else ('Not Targeted' if normalized_status == 'false' else 'Unknown')
        )
        tone = 'warning' if normalized_status == 'true' else ('normal' if normalized_status == 'false' else 'unknown')
    else:
        label = status
        tone = 'unknown'

    return {
        'type': condition_type,
        'status': status,
        'state_label': label,
        'state_tone': tone,
        'reason': reason,
        'message': condition.get('message'),
        'last_transition_time': parse_inventory_datetime(condition.get('last_transition_time')),
    }


def container_presentation(container: dict[str, Any]) -> dict[str, Any]:
    state = str(container.get('state') or 'Unknown')
    normalized_state = state.casefold()
    reason = str(container.get('reason') or '').casefold()
    exit_code = container.get('exit_code')
    ready = bool(container.get('ready'))

    if normalized_state == 'running':
        label = 'Ready' if ready else 'Not Ready'
        tone = 'normal' if ready else 'warning'
    elif normalized_state == 'waiting' and reason in CRITICAL_WAITING_REASONS:
        label = str(container.get('reason') or 'Runtime Failure')
        tone = 'critical'
    elif normalized_state == 'waiting':
        label = 'Waiting'
        tone = 'pending'
    elif normalized_state == 'terminated' and exit_code in (0, '0'):
        label = 'Completed'
        tone = 'info'
    elif normalized_state == 'terminated' and exit_code is not None:
        label = 'Failed'
        tone = 'critical'
    elif normalized_state in {'not reported', 'unknown'} or exit_code is None:
        label = 'Unknown'
        tone = 'unknown'
    else:
        label = state
        tone = 'unknown'

    restart_count = int(container.get('restart_count') or 0)
    result = dict(container)
    result.update(
        {
            'kind': str(container.get('kind') or 'Regular'),
            'runtime_state_label': label,
            'runtime_state_tone': tone,
            'started_at_value': parse_inventory_datetime(container.get('started_at')),
            'finished_at_value': parse_inventory_datetime(container.get('finished_at')),
            'restart_activity': f'{restart_count} Restart' + ('' if restart_count == 1 else 's'),
        }
    )
    return result


def operational_context(
    state_label: str,
    restart_count: int,
    runtime_evidence_reported: bool,
    owner_resolution_review: bool,
) -> dict[str, str]:
    contexts = {
        'Failed': (
            'Investigate Pod Failure',
            'Review container exit codes, image delivery, volume mounts, placement constraints, '
            'and owning workload events.',
            'circle-x',
            'critical',
        ),
        'Not Ready': (
            'Investigate Pod Readiness',
            'Review container readiness, Pod conditions, probe failures, and runtime reasons '
            'before treating the Pod as available.',
            'shield-alert',
            'warning',
        ),
        'Starting': (
            'Validate Pod Startup',
            'Confirm scheduling, image pull, initialization, and volume attachment continue progressing.',
            'loader-circle',
            'warning',
        ),
        'Terminating': (
            'Validate Pod Termination',
            'Confirm workload replacement, finalizers, volume detach, and termination grace '
            'behavior complete as expected.',
            'hourglass',
            'warning',
        ),
        'Completed': (
            'Completed Pod Snapshot',
            'The Pod completed successfully in the committed snapshot. Confirm retention and '
            'cleanup follow the owning workload policy.',
            'circle-check-big',
            'info',
        ),
        'Unknown': (
            'Validate Pod Runtime Evidence',
            'Pod runtime state could not be established from phase and container readiness '
            'evidence. Refresh inventory before making availability decisions.',
            'circle-help',
            'warning',
        ),
    }
    if state_label in contexts:
        title, description, icon, tone = contexts[state_label]
    elif not runtime_evidence_reported:
        title, description, icon, tone = (
            'Refresh Container Runtime Evidence',
            'Container runtime evidence was not reported. Refresh inventory before making '
            'runtime availability decisions.',
            'refresh-cw',
            'warning',
        )
    elif restart_count > 0:
        title, description, icon, tone = (
            'Review Restart Activity',
            'The committed snapshot reports container restarts. Review current runtime reasons '
            'before concluding the issue is active.',
            'rotate-ccw',
            'warning',
        )
    elif owner_resolution_review:
        title, description, icon, tone = (
            'Validate Pod Owner Resolution',
            'The direct owner is available, but higher-level Deployment or CronJob resolution was not fully collected.',
            'git-branch',
            'warning',
        )
    else:
        title, description, icon, tone = (
            'Pod Snapshot Ready for Review',
            'No exceptional runtime signal is present in the current committed inventory snapshot.',
            'circle-check',
            'normal',
        )
    return {'title': title, 'description': description, 'icon': icon, 'tone': tone}
