from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_TELEGRAM_API: Final = 'https://api.telegram.org'
_GITHUB_API: Final = 'https://api.github.com'
_TRUE_VALUES: Final = frozenset({'1', 'true', 'yes', 'on'})
_FAILURE_RESULTS: Final = frozenset(
    {'failure', 'cancelled', 'timed_out', 'action_required'}
)

_EVENT_TITLES: Final = {
    'FULL_ADMISSION_PASSED': '✅ KAORI · Full Admission Passed',
    'SECURITY_GATE_FAILED': '🔐 KAORI · Security Gate Failed',
    'DELIVERY_FAILED': '❌ KAORI · Delivery Failed',
    'UAT_REQUIRED': '🧪 KAORI · UAT Required',
    'PROMOTION_VALIDATED': '✅ KAORI · Promotion Validated',
    'PROMOTION_SUCCEEDED': '🚀 KAORI · Promotion Succeeded',
}

_EVENT_CATEGORIES: Final = {
    'FULL_ADMISSION_PASSED': 'CI / Quality',
    'DELIVERY_FAILED': 'CI / Quality',
    'SECURITY_GATE_FAILED': 'Security',
    'UAT_REQUIRED': 'UAT',
    'PROMOTION_VALIDATED': 'Promotion',
    'PROMOTION_SUCCEEDED': 'Promotion',
}

_PROFILE_CONTEXT: Final = {
    'pr-integration': ('PR Integration', 'Staging Candidate'),
    'staging-integration': ('Staging Integration', 'Staging'),
    'promotion': ('Promotion', 'Main Promotion'),
    'post-promotion': ('Post-promotion', 'Main'),
}

_ACTIONS: Final = {
    'FULL_ADMISSION_PASSED': (
        'Review the final candidate and merge to kaori/staging when approved.'
    ),
    'SECURITY_GATE_FAILED': (
        'Review security evidence, repair the finding, then rerun Admission.'
    ),
    'DELIVERY_FAILED': (
        'Review the first failing delivery gate, repair it, then rerun Admission.'
    ),
    'UAT_REQUIRED': 'Complete UAT before promotion to main.',
    'PROMOTION_VALIDATED': 'Merge the accepted staging lineage to main.',
    'PROMOTION_SUCCEEDED': (
        'No delivery action required; promoted lineage is verified on main.'
    ),
}

_FULL_GATE_NAMES: Final = (
    'Static, Architecture, and Governance',
    'Secrets, SAST, Dependencies, and Workflow Security',
    'Functional and Integration Tests',
    'Frontend Reproducibility',
    'Production Image, Container Security, Runtime, and DAST',
)
_FAILURE_ORDER: Final = (
    'Resolve KAORI Validation Profile',
    *_FULL_GATE_NAMES,
    'KAORI Fast Integration Smoke',
    'KAORI CI Admission',
)


def select_event(
    *,
    profile: str,
    execution: str,
    admission_result: str,
    security_result: str,
) -> str | None:
    if admission_result in _FAILURE_RESULTS:
        if security_result == 'failure':
            return 'SECURITY_GATE_FAILED'
        return 'DELIVERY_FAILED'
    if admission_result != 'success':
        return None

    if profile == 'staging-integration':
        return 'UAT_REQUIRED'
    if profile == 'promotion':
        return 'PROMOTION_VALIDATED'
    if profile == 'post-promotion':
        return 'PROMOTION_SUCCEEDED'
    if profile == 'pr-integration' and execution == 'full':
        return 'FULL_ADMISSION_PASSED'
    return None


def resolve_profile(*, event_name: str, head_branch: str, base_branch: str) -> str:
    if event_name == 'pull_request' and base_branch == 'kaori/staging':
        return 'pr-integration'
    if (
        event_name == 'pull_request'
        and base_branch == 'main'
        and head_branch == 'kaori/staging'
    ):
        return 'promotion'
    if event_name == 'push' and head_branch == 'kaori/staging':
        return 'staging-integration'
    if event_name == 'push' and head_branch == 'main':
        return 'post-promotion'
    return 'full'


def event_category(event: str) -> str:
    return _EVENT_CATEGORIES.get(event, 'CI / Quality')


def configuration_status(
    *,
    enabled: str,
    bot_token: str,
    chat_id: str,
    topic_id: str,
) -> tuple[bool, str]:
    if enabled.strip().lower() not in _TRUE_VALUES:
        return False, 'Telegram GitHub Actions notifications are not enabled.'
    if not bot_token.strip() or not chat_id.strip() or not topic_id.strip():
        return False, 'Telegram GitHub Actions notification configuration is incomplete.'
    return True, 'Telegram GitHub Actions notifications are configured.'


def render_message(
    *,
    event: str,
    profile: str,
    execution: str,
    source_sha: str,
    repository: str,
    run_url: str,
    pr_number: str,
    failure_detail: str = '',
) -> str:
    title = _EVENT_TITLES.get(
        event,
        f'ℹ️ KAORI · {event.replace("_", " ").title()}',
    )
    boundary, environment = _PROFILE_CONTEXT.get(
        profile,
        (profile or 'Delivery', 'Delivery'),
    )
    result = 'FAIL' if event in {'SECURITY_GATE_FAILED', 'DELIVERY_FAILED'} else 'PASS'
    short_sha = source_sha[:12] if source_sha else 'unknown'

    lines = [
        title,
        '',
        f'Category: {event_category(event)}',
        f'Boundary: {boundary}',
        f'Environment: {environment}',
        f'Result: {result}',
        f'Commit: {short_sha}',
        f'Repository: {repository}',
    ]
    if pr_number.strip():
        lines.append(f'PR: #{pr_number.strip()}')

    evidence = _evidence_summary(event=event, execution=execution)
    if evidence:
        lines.append(f'Evidence: {evidence}')
    if failure_detail.strip() and result == 'FAIL':
        lines.append(f'First Failure: {failure_detail.strip()}')

    lines.append(f'Action: {_ACTIONS.get(event, "Review the workflow result.")}')
    if run_url.strip():
        lines.extend(['', f'View Run: {run_url.strip()}'])
    return '\n'.join(lines).strip()


def _evidence_summary(*, event: str, execution: str) -> str:
    if event == 'FULL_ADMISSION_PASSED':
        return 'Fresh Full Admission PASS'
    if event in {'UAT_REQUIRED', 'PROMOTION_VALIDATED', 'PROMOTION_SUCCEEDED'}:
        if execution == 'fast':
            return 'Full Admission evidence reused + Fast Integration Smoke PASS'
        return 'Selected Admission path PASS'
    if event in {'SECURITY_GATE_FAILED', 'DELIVERY_FAILED'}:
        return 'Selected Admission path failed'
    return ''


def infer_execution(jobs: list[dict[str, Any]]) -> str:
    conclusions = _job_conclusions(jobs)
    if conclusions.get('KAORI Fast Integration Smoke') == 'success':
        return 'fast'
    return 'full'


def first_failure(jobs: list[dict[str, Any]]) -> str:
    conclusions = _job_conclusions(jobs)
    for name in _FAILURE_ORDER:
        conclusion = conclusions.get(name, '')
        if conclusion in _FAILURE_RESULTS:
            return f'{name} — {conclusion}'
    return ''


def _job_conclusions(jobs: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(job.get('name') or ''): str(job.get('conclusion') or '')
        for job in jobs
        if isinstance(job, dict) and job.get('name')
    }


def fetch_workflow_jobs(
    *,
    repository: str,
    run_id: str,
    token: str,
) -> list[dict[str, Any]]:
    if not token.strip():
        raise RuntimeError('GitHub Actions read token is unavailable.')
    safe_repository = '/'.join(
        quote(part, safe='') for part in repository.split('/', 1)
    )
    safe_run_id = quote(str(run_id), safe='')
    url = f'{_GITHUB_API}/repos/{safe_repository}/actions/runs/{safe_run_id}/jobs?per_page=100'
    request = Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
        },
        method='GET',
    )
    try:
        with urlopen(  # noqa: S310  # nosec B310 - fixed GitHub HTTPS authority
            request,
            timeout=10,
        ) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise RuntimeError(
            f'GitHub Actions job lookup failed with HTTP {exc.code}.'
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(
            'GitHub Actions job lookup is unavailable or invalid.'
        ) from exc

    jobs = payload.get('jobs') if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise RuntimeError('GitHub Actions job lookup returned an invalid payload.')
    return [job for job in jobs if isinstance(job, dict)]


def send_message(
    *,
    bot_token: str,
    chat_id: str,
    topic_id: str,
    message: str,
    timeout_seconds: int = 10,
) -> tuple[bool, str]:
    body = urlencode(
        {
            'chat_id': chat_id,
            'message_thread_id': topic_id,
            'text': message,
            'link_preview_options': json.dumps(
                {'is_disabled': True},
                separators=(',', ':'),
            ),
        }
    ).encode('utf-8')
    request = Request(
        f'{_TELEGRAM_API}/bot{bot_token}/sendMessage',
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(  # noqa: S310  # nosec B310 - fixed Telegram HTTPS authority
            request,
            timeout=max(int(timeout_seconds), 1),
        ) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        return False, f'Telegram rejected the notification with HTTP {exc.code}.'
    except (URLError, TimeoutError, OSError, ValueError):
        return False, 'Telegram is unreachable or returned an invalid response.'

    if not isinstance(payload, dict) or not bool(payload.get('ok')):
        return False, 'Telegram rejected the notification.'
    return True, 'Telegram GitHub Actions notification sent.'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Send categorized KAORI GitHub Actions notifications to a Telegram topic.'
        )
    )
    parser.add_argument('--workflow-run-id', default='')
    parser.add_argument('--workflow-event', default='')
    parser.add_argument('--workflow-conclusion', default='')
    parser.add_argument('--head-branch', default='')
    parser.add_argument('--base-branch', default='')
    parser.add_argument('--profile', default='')
    parser.add_argument('--execution', default='')
    parser.add_argument('--admission-result', default='')
    parser.add_argument('--security-result', default='skipped')
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--run-url', required=True)
    parser.add_argument('--pr-number', default='')
    parser.add_argument('--failure-detail', default='')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    topic_id = os.environ.get('TELEGRAM_GITHUB_ACTIONS_TOPIC_ID', '')
    enabled = os.environ.get('TELEGRAM_NOTIFICATIONS_ENABLED', '')
    configured, reason = configuration_status(
        enabled=enabled,
        bot_token=bot_token,
        chat_id=chat_id,
        topic_id=topic_id,
    )
    if not configured:
        print(f'SKIP — {reason}')
        return 0

    profile = args.profile
    execution = args.execution
    admission_result = args.admission_result
    security_result = args.security_result
    failure_detail = args.failure_detail

    if args.workflow_run_id:
        try:
            jobs = fetch_workflow_jobs(
                repository=args.repository,
                run_id=args.workflow_run_id,
                token=os.environ.get('GH_TOKEN', ''),
            )
        except RuntimeError as exc:
            print(f'FAIL — {exc}', file=sys.stderr)
            return 1
        conclusions = _job_conclusions(jobs)
        profile = resolve_profile(
            event_name=args.workflow_event,
            head_branch=args.head_branch,
            base_branch=args.base_branch,
        )
        execution = infer_execution(jobs)
        admission_result = conclusions.get('KAORI CI Admission', '')
        if (
            admission_result not in _FAILURE_RESULTS | {'success'}
            and args.workflow_conclusion in _FAILURE_RESULTS
        ):
            admission_result = args.workflow_conclusion
        security_result = conclusions.get(
            'Secrets, SAST, Dependencies, and Workflow Security',
            'skipped',
        )
        failure_detail = first_failure(jobs)

    event = select_event(
        profile=profile,
        execution=execution,
        admission_result=admission_result,
        security_result=security_result,
    )
    if event is None:
        print(
            'SKIP — Completed KAORI CI run has no actionable GitHub Actions notification.'
        )
        return 0

    message = render_message(
        event=event,
        profile=profile,
        execution=execution,
        source_sha=args.source_sha,
        repository=args.repository,
        run_url=args.run_url,
        pr_number=args.pr_number,
        failure_detail=failure_detail,
    )
    delivered, detail = send_message(
        bot_token=bot_token,
        chat_id=chat_id,
        topic_id=topic_id,
        message=message,
    )
    if not delivered:
        print(f'FAIL — {detail}', file=sys.stderr)
        return 1
    print(f'PASS — {detail} Category={event_category(event)} Event={event}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
