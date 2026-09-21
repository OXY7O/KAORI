from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Final, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    from ci_delivery_context import (
        DeliveryContext,
        fetch_notification_artifacts,
        fetch_recent_pr_quality_runs,
        pr_run_profile,
        resolve_delivery_context,
        safe_repository,
        select_unnotified_pr_failure,
    )
except ModuleNotFoundError:
    from scripts.ci_delivery_context import (
        DeliveryContext,
        fetch_notification_artifacts,
        fetch_recent_pr_quality_runs,
        pr_run_profile,
        resolve_delivery_context,
        safe_repository,
        select_unnotified_pr_failure,
    )

_TELEGRAM_API: Final = 'https://api.telegram.org'
_TRUE_VALUES: Final = frozenset({'1', 'true', 'yes', 'on'})
_FAILURE_RESULTS: Final = frozenset({'failure', 'timed_out', 'action_required'})

_EVENT_TITLES: Final = {
    'CANDIDATE_BLOCKED': '❌ KAORI · Candidate Blocked',
    'STAGING_DELIVERY_FAILED': '❌ KAORI · Staging Delivery Failed',
    'PROMOTION_BLOCKED': '❌ KAORI · Promotion Blocked',
    'PRODUCTION_VERIFICATION_FAILED': '❌ KAORI · Production Lineage Verification Failed',
    'UAT_REQUIRED': '🧪 KAORI · Ready for UAT',
    'DELIVERY_COMPLETE': '🚀 KAORI · Delivery Complete',
}

_EVENT_CATEGORIES: Final = {
    'CANDIDATE_BLOCKED': 'CI / Quality',
    'STAGING_DELIVERY_FAILED': 'CI / Quality',
    'PROMOTION_BLOCKED': 'Promotion',
    'PRODUCTION_VERIFICATION_FAILED': 'Promotion',
    'UAT_REQUIRED': 'UAT',
    'DELIVERY_COMPLETE': 'Promotion',
}

_PROFILE_CONTEXT: Final = {
    'pr-integration': ('Full Admission', 'PR → kaori/staging'),
    'staging-integration': ('Staging Integration', 'kaori/staging'),
    'promotion': ('Promotion Validation', 'kaori/staging → main'),
    'post-promotion': ('Post-promotion', 'main'),
}

_EVENT_STATUS: Final = {
    'CANDIDATE_BLOCKED': 'BLOCKED',
    'STAGING_DELIVERY_FAILED': 'FAILED',
    'PROMOTION_BLOCKED': 'BLOCKED',
    'PRODUCTION_VERIFICATION_FAILED': 'FAILED',
    'UAT_REQUIRED': 'READY FOR UAT',
    'DELIVERY_COMPLETE': 'COMPLETE',
}

_ACTIONS: Final = {
    'CANDIDATE_BLOCKED': 'Return the work to Draft repair, pass Developer Check, then freeze a new Ready candidate.',
    'STAGING_DELIVERY_FAILED': 'Do not perform UAT. Repair the staging delivery failure before continuing.',
    'PROMOTION_BLOCKED': 'Keep main unchanged. Repair the promotion candidate and rerun governed validation.',
    'PRODUCTION_VERIFICATION_FAILED': 'Review production-lineage verification before declaring the delivery complete.',
    'UAT_REQUIRED': 'Complete human UAT before promotion to main.',
    'DELIVERY_COMPLETE': 'No delivery action required; the accepted lineage is verified on main.',
}

_FAILURE_ORDER: Final = (
    'Resolve Profile',
    'Static & Governance',
    'Security',
    'Functional Tests',
    'Frontend',
    'Runtime & DAST',
    'Fast Smoke',
    'CI Admission',
    'Resolve KAORI Validation Profile',
    'Static, Architecture, and Governance',
    'Secrets, SAST, Dependencies, and Workflow Security',
    'Functional and Integration Tests',
    'Frontend Reproducibility',
    'Production Image, Container Security, Runtime, and DAST',
    'KAORI Fast Integration Smoke',
    'KAORI CI Admission',
)


class TransportConfig:
    __slots__ = ('bot_token', 'chat_id', 'topic_id')

    def __init__(self, *, bot_token: str, chat_id: str, topic_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.topic_id = topic_id


class DeliveryNotice(TypedDict):
    event: str
    profile: str
    execution: str
    source_sha: str
    repository: str
    run_url: str
    context: DeliveryContext
    failure_detail: str


def select_event(
    *,
    profile: str,
    execution: str,
    admission_result: str,
    security_result: str,
) -> str | None:
    del execution, security_result
    if admission_result in _FAILURE_RESULTS:
        return {
            'pr-integration': 'CANDIDATE_BLOCKED',
            'staging-integration': 'STAGING_DELIVERY_FAILED',
            'promotion': 'PROMOTION_BLOCKED',
            'post-promotion': 'PRODUCTION_VERIFICATION_FAILED',
        }.get(profile)
    if admission_result != 'success':
        return None
    if profile == 'staging-integration':
        return 'UAT_REQUIRED'
    if profile == 'post-promotion':
        return 'DELIVERY_COMPLETE'
    return None


def resolve_profile(*, event_name: str, head_branch: str, base_branch: str) -> str:
    if event_name == 'push' and head_branch == 'kaori/staging':
        return 'staging-integration'
    if event_name == 'push' and head_branch == 'main':
        return 'post-promotion'
    if event_name == 'pull_request' and base_branch == 'kaori/staging':
        return 'pr-integration'
    if event_name == 'pull_request' and base_branch == 'main' and head_branch == 'kaori/staging':
        return 'promotion'
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
    context: DeliveryContext,
    failure_detail: str = '',
) -> str:
    title = _EVENT_TITLES.get(event, f'ℹ️ KAORI · {event.replace("_", " ").title()}')
    stage, environment = _PROFILE_CONTEXT.get(profile, (profile or 'Delivery', repository))
    short_sha = source_sha[:12] if source_sha else 'unknown'
    lines = [title, '', '📌 Work', _work_summary(context)]
    lines.extend(
        [
            '',
            '📍 Delivery',
            f'Stage: {stage}',
            f'Status: {_EVENT_STATUS.get(event, "INFO")}',
            f'Environment: {environment}',
            '',
            '🧪 Testing',
        ]
    )
    lines.extend(_testing_lines(event=event, context=context))
    if failure_detail.strip() and event not in {'UAT_REQUIRED', 'DELIVERY_COMPLETE'}:
        lines.extend(['', '🚨 Failure', f'Failure: {failure_detail.strip()}'])
    lines.extend(['', '✅ Evidence'])
    evidence = _evidence_summary(event=event, execution=execution)
    if evidence:
        lines.append(evidence)
    lines.extend([f'Commit: {short_sha}', '', '➡️ Next', _ACTIONS.get(event, 'Review the workflow result.')])
    lines.extend(['', '🔗 Tracking', *_tracking_lines(context=context, run_url=run_url)])
    return '\n'.join(lines).strip()


def _work_summary(context: DeliveryContext) -> str:
    if context.issue_number and context.issue_title:
        return f'#{context.issue_number} {context.issue_title}'
    if context.pr_number and context.pr_title:
        return f'PR #{context.pr_number} {context.pr_title}'
    return 'Delivery context unavailable'


def _testing_lines(*, event: str, context: DeliveryContext) -> list[str]:
    if event == 'UAT_REQUIRED':
        guidance = context.test_guidance or context.issue_title or context.pr_title or 'the linked delivery scope'
        return ['Ready for UAT', f'Validate: {guidance}']
    if event == 'DELIVERY_COMPLETE':
        return ['No additional delivery test required']
    return ['Do not test yet']


def _tracking_lines(*, context: DeliveryContext, run_url: str) -> list[str]:
    lines: list[str] = []
    if context.issue_number:
        lines.append(f'Issue: #{context.issue_number} · {context.issue_status or "Unknown"}')
        if context.issue_url:
            lines.append(context.issue_url)
    if context.pr_number:
        lines.append(f'PR: #{context.pr_number} · {context.pr_status or "Unknown"}')
        if context.pr_url:
            lines.append(context.pr_url)
    if run_url.strip():
        lines.append(f'CI: {run_url.strip()}')
    return lines


def _evidence_summary(*, event: str, execution: str) -> str:
    if event == 'UAT_REQUIRED':
        if execution == 'fast':
            return 'Full Admission evidence reused + Fast Integration Smoke PASS'
        return 'Selected Admission path PASS'
    if event == 'DELIVERY_COMPLETE':
        if execution == 'fast':
            return 'Accepted staging lineage reused + Fast Integration Smoke PASS + production lineage verified'
        return 'Production lineage verified'
    return {
        'CANDIDATE_BLOCKED': 'Full Admission did not complete successfully',
        'STAGING_DELIVERY_FAILED': 'Staging integration did not complete successfully',
        'PROMOTION_BLOCKED': 'Promotion validation did not complete successfully',
        'PRODUCTION_VERIFICATION_FAILED': 'Post-promotion verification did not complete successfully',
    }.get(event, '')


def infer_execution(jobs: list[dict[str, Any]]) -> str:
    conclusions = _job_conclusions(jobs)
    if conclusions.get('Fast Smoke') == 'success' or conclusions.get('KAORI Fast Integration Smoke') == 'success':
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


def _github_api_get(*, path: str, token: str) -> Any:
    from ci_delivery_context import github_api_get

    return github_api_get(path=path, token=token)


def fetch_workflow_jobs(
    *,
    repository: str,
    run_id: str,
    token: str,
) -> list[dict[str, Any]]:
    safe_run_id = quote(str(run_id), safe='')
    payload = _github_api_get(
        path=f'/repos/{safe_repository(repository)}/actions/runs/{safe_run_id}/jobs?per_page=100',
        token=token,
    )
    jobs = payload.get('jobs') if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise RuntimeError('GitHub Actions job lookup returned an invalid payload.')
    return [job for job in jobs if isinstance(job, dict)]


def fetch_workflow_run(
    *,
    repository: str,
    run_id: str,
    token: str,
) -> dict[str, Any]:
    safe_run_id = quote(str(run_id), safe='')
    payload = _github_api_get(
        path=f'/repos/{safe_repository(repository)}/actions/runs/{safe_run_id}',
        token=token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError('GitHub Actions workflow run lookup returned an invalid payload.')
    return payload


def validate_trusted_quality_workflow_run(
    *,
    workflow_run: dict[str, Any],
    source_sha: str,
    head_branch: str,
) -> None:
    head_repository = workflow_run.get('head_repository')
    repository_name = (
        str(head_repository.get('full_name') or '')
        if isinstance(head_repository, dict)
        else ''
    )
    if str(workflow_run.get('name') or '') != 'KAORI CI':
        raise RuntimeError('Workflow run is not KAORI CI.')
    if str(workflow_run.get('path') or '') != '.github/workflows/quality.yml':
        raise RuntimeError('Workflow run does not use the canonical KAORI CI workflow path.')
    if str(workflow_run.get('event') or '') != 'push':
        raise RuntimeError('Workflow run is not a trusted push execution.')
    if str(workflow_run.get('status') or '') != 'completed':
        raise RuntimeError('Workflow run is not completed.')
    if repository_name != 'OXY7O/KAORI':
        raise RuntimeError('Workflow run source repository is not trusted.')
    if str(workflow_run.get('head_sha') or '') != source_sha:
        raise RuntimeError('Workflow run source SHA does not match the notification source SHA.')
    if str(workflow_run.get('head_branch') or '') != head_branch:
        raise RuntimeError('Workflow run branch does not match the notification branch.')
    if head_branch not in {'kaori/staging', 'main'}:
        raise RuntimeError('Workflow run branch is not a trusted notification branch.')


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
            'link_preview_options': json.dumps({'is_disabled': True}, separators=(',', ':')),
        }
    ).encode('utf-8')
    request = Request(
        f'{_TELEGRAM_API}/bot{bot_token}/sendMessage',
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        # B310 is reviewed here because the request is fixed to Telegram's HTTPS API authority.
        with urlopen(  # noqa: S310  # nosec B310
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


def _delivery_results(
    *,
    jobs: list[dict[str, Any]],
    workflow_conclusion: str,
) -> tuple[str, str, str, str]:
    conclusions = _job_conclusions(jobs)
    admission_result = conclusions.get('CI Admission') or conclusions.get('KAORI CI Admission', '')
    if admission_result not in _FAILURE_RESULTS | {'success'} and workflow_conclusion in _FAILURE_RESULTS:
        admission_result = workflow_conclusion
    security_result = conclusions.get(
        'Security',
        conclusions.get('Secrets, SAST, Dependencies, and Workflow Security', 'skipped'),
    )
    return infer_execution(jobs), admission_result, security_result, first_failure(jobs)


def _emit_notification(*, notice: DeliveryNotice, transport: TransportConfig) -> int:
    message = render_message(
        event=notice['event'],
        profile=notice['profile'],
        execution=notice['execution'],
        source_sha=notice['source_sha'],
        repository=notice['repository'],
        run_url=notice['run_url'],
        context=notice['context'],
        failure_detail=notice['failure_detail'],
    )
    delivered, detail = send_message(
        bot_token=transport.bot_token,
        chat_id=transport.chat_id,
        topic_id=transport.topic_id,
        message=message,
    )
    if not delivered:
        print(f'FAIL — {detail}', file=sys.stderr)
        return 1
    print(f'PASS — {detail} Category={event_category(notice["event"])} Event={notice["event"]}.')
    return 0


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get('GITHUB_OUTPUT', '')
    if not output_path or not value:
        return
    with open(output_path, 'a', encoding='utf-8') as output:  # noqa: PTH123
        output.write(f'{name}={value}\n')


def _scan_pr_failures(
    *,
    repository: str,
    token: str,
    transport: TransportConfig,
) -> int:
    try:
        selected = select_unnotified_pr_failure(
            runs=fetch_recent_pr_quality_runs(repository=repository, token=token),
            artifacts=fetch_notification_artifacts(repository=repository, token=token),
        )
        if selected is None:
            print('SKIP — No unnotified actionable PR delivery failure found.')
            return 0
        run_id = str(selected.get('id') or '')
        jobs = fetch_workflow_jobs(repository=repository, run_id=run_id, token=token)
        profile = pr_run_profile(selected)
        execution, admission_result, security_result, failure_detail = _delivery_results(
            jobs=jobs,
            workflow_conclusion=str(selected.get('conclusion') or ''),
        )
        event = select_event(
            profile=profile,
            execution=execution,
            admission_result=admission_result,
            security_result=security_result,
        )
        if event is None:
            print('SKIP — Selected PR run has no actionable Telegram event.')
            return 0
        pull_requests = selected.get('pull_requests')
        pr_number = ''
        if isinstance(pull_requests, list) and pull_requests and isinstance(pull_requests[0], dict):
            pr_number = str(pull_requests[0].get('number') or '')
        source_sha = str(selected.get('head_sha') or '')
        context = resolve_delivery_context(
            repository=repository,
            source_sha=source_sha,
            profile=profile,
            token=token,
            pr_number=pr_number,
        )
        notice: DeliveryNotice = {
            'event': event,
            'profile': profile,
            'execution': execution,
            'source_sha': source_sha,
            'repository': repository,
            'run_url': str(selected.get('html_url') or ''),
            'context': context,
            'failure_detail': failure_detail,
        }
    except RuntimeError as exc:
        print(f'FAIL — {exc}', file=sys.stderr)
        return 1
    result = _emit_notification(notice=notice, transport=transport)
    if result == 0:
        _write_output('quality_run_id', run_id)
    return result


def _notify_trusted_push(
    *,
    args: argparse.Namespace,
    token: str,
    transport: TransportConfig,
) -> int:
    try:
        workflow_run = fetch_workflow_run(
            repository=args.repository,
            run_id=args.workflow_run_id,
            token=token,
        )
        validate_trusted_quality_workflow_run(
            workflow_run=workflow_run,
            source_sha=args.source_sha,
            head_branch=args.head_branch,
        )
        jobs = fetch_workflow_jobs(
            repository=args.repository,
            run_id=args.workflow_run_id,
            token=token,
        )
        profile = resolve_profile(
            event_name=args.workflow_event,
            head_branch=args.head_branch,
            base_branch=args.base_branch,
        )
        execution, admission_result, security_result, failure_detail = _delivery_results(
            jobs=jobs,
            workflow_conclusion=str(workflow_run.get('conclusion') or ''),
        )
        event = select_event(
            profile=profile,
            execution=execution,
            admission_result=admission_result,
            security_result=security_result,
        )
        if event is None:
            print('SKIP — Completed KAORI CI run has no trusted delivery Telegram notification.')
            return 0
        context = resolve_delivery_context(
            repository=args.repository,
            source_sha=args.source_sha,
            profile=profile,
            token=token,
            pr_number=args.pr_number,
        )
        notice: DeliveryNotice = {
            'event': event,
            'profile': profile,
            'execution': execution,
            'source_sha': args.source_sha,
            'repository': args.repository,
            'run_url': str(workflow_run.get('html_url') or ''),
            'context': context,
            'failure_detail': failure_detail,
        }
    except RuntimeError as exc:
        print(f'FAIL — {exc}', file=sys.stderr)
        return 1
    return _emit_notification(notice=notice, transport=transport)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Send trusted KAORI GitHub Actions delivery notifications to a Telegram topic.'
    )
    parser.add_argument('--workflow-run-id', default='')
    parser.add_argument('--scan-pr-failures', action='store_true')
    parser.add_argument('--workflow-event', default='')
    parser.add_argument('--head-branch', default='')
    parser.add_argument('--base-branch', default='')
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--pr-number', default='')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    transport = TransportConfig(
        bot_token=os.environ.get('TELEGRAM_BOT_TOKEN', ''),
        chat_id=os.environ.get('TELEGRAM_CHAT_ID', ''),
        topic_id=os.environ.get('TELEGRAM_GITHUB_ACTIONS_TOPIC_ID', ''),
    )
    configured, reason = configuration_status(
        enabled=os.environ.get('TELEGRAM_NOTIFICATIONS_ENABLED', ''),
        bot_token=transport.bot_token,
        chat_id=transport.chat_id,
        topic_id=transport.topic_id,
    )
    if not configured:
        print(f'SKIP — {reason}')
        return 0
    token = os.environ.get('GH_TOKEN', '')
    if args.scan_pr_failures:
        return _scan_pr_failures(repository=args.repository, token=token, transport=transport)
    if args.workflow_run_id:
        return _notify_trusted_push(args=args, token=token, transport=transport)
    print('SKIP — No Telegram delivery notification mode was requested.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
