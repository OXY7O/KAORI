from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_TELEGRAM_API: Final = 'https://api.telegram.org'
_TRUE_VALUES: Final = frozenset({'1', 'true', 'yes', 'on'})

_EVENT_TITLES: Final = {
    'FULL_ADMISSION_PASSED': '✅ KAORI · Full Admission Passed',
    'SECURITY_GATE_FAILED': '🔐 KAORI · Security Gate Failed',
    'DELIVERY_FAILED': '❌ KAORI · Delivery Failed',
    'UAT_REQUIRED': '🧪 KAORI · UAT Required',
    'PROMOTION_VALIDATED': '✅ KAORI · Promotion Validated',
    'PROMOTION_SUCCEEDED': '🚀 KAORI · Promotion Succeeded',
}

_PROFILE_CONTEXT: Final = {
    'pr-integration': ('PR Integration', 'Staging Candidate'),
    'staging-integration': ('Staging Integration', 'Staging'),
    'promotion': ('Promotion', 'Main Promotion'),
    'post-promotion': ('Post-promotion', 'Main'),
}

_ACTIONS: Final = {
    'FULL_ADMISSION_PASSED': 'Review the final candidate and merge to kaori/staging when approved.',
    'SECURITY_GATE_FAILED': 'Review security evidence, repair the finding, then rerun Admission.',
    'DELIVERY_FAILED': 'Review the first failing delivery gate, repair it, then rerun Admission.',
    'UAT_REQUIRED': 'Complete UAT before promotion to main.',
    'PROMOTION_VALIDATED': 'Merge the accepted staging lineage to main.',
    'PROMOTION_SUCCEEDED': 'No delivery action required; promoted lineage is verified on main.',
}


def select_event(
    *,
    profile: str,
    execution: str,
    admission_result: str,
    security_result: str,
) -> str | None:
    if admission_result != 'success':
        if security_result == 'failure':
            return 'SECURITY_GATE_FAILED'
        return 'DELIVERY_FAILED'

    if profile == 'staging-integration':
        return 'UAT_REQUIRED'
    if profile == 'promotion':
        return 'PROMOTION_VALIDATED'
    if profile == 'post-promotion':
        return 'PROMOTION_SUCCEEDED'
    if profile == 'pr-integration' and execution == 'full':
        return 'FULL_ADMISSION_PASSED'
    return None


def configuration_status(*, enabled: str, bot_token: str, chat_id: str) -> tuple[bool, str]:
    if enabled.strip().lower() not in _TRUE_VALUES:
        return False, 'Telegram delivery is not enabled.'
    if not bot_token.strip() or not chat_id.strip():
        return False, 'Telegram delivery configuration is incomplete.'
    return True, 'Telegram delivery is configured.'


def render_message(
    *,
    event: str,
    profile: str,
    execution: str,
    source_sha: str,
    repository: str,
    run_url: str,
    pr_number: str,
    uat_url: str,
) -> str:
    title = _EVENT_TITLES.get(event, f'ℹ️ KAORI · {event.replace("_", " ").title()}')
    boundary, environment = _PROFILE_CONTEXT.get(profile, (profile or 'Delivery', 'Delivery'))
    result = 'FAIL' if event in {'SECURITY_GATE_FAILED', 'DELIVERY_FAILED'} else 'PASS'
    short_sha = source_sha[:12] if source_sha else 'unknown'

    lines = [
        title,
        '',
        f'Event: {event}',
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
    lines.append(f'Action: {_ACTIONS.get(event, "Review the workflow result.")}')

    if run_url.strip():
        lines.extend(['', f'View Run: {run_url.strip()}'])
    if event == 'UAT_REQUIRED' and uat_url.strip():
        lines.append(f'Open KAORI UAT: {uat_url.strip()}')
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


def send_message(
    *,
    bot_token: str,
    chat_id: str,
    message: str,
    timeout_seconds: int = 10,
) -> tuple[bool, str]:
    body = urlencode({'chat_id': chat_id, 'text': message, 'link_preview_options': json.dumps({'is_disabled': True})}).encode(
        'utf-8'
    )
    request = Request(
        f'{_TELEGRAM_API}/bot{bot_token}/sendMessage',
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(  # noqa: S310  # nosec B310 - fixed HTTPS Telegram authority
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
    return True, 'Telegram delivery notification sent.'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Send actionable KAORI delivery notifications to Telegram.')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--execution', required=True)
    parser.add_argument('--admission-result', required=True)
    parser.add_argument('--security-result', default='skipped')
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--run-url', required=True)
    parser.add_argument('--pr-number', default='')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    event = select_event(
        profile=args.profile,
        execution=args.execution,
        admission_result=args.admission_result,
        security_result=args.security_result,
    )
    if event is None:
        print('SKIP — Current Admission boundary has no actionable Telegram delivery event.')
        return 0

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_DELIVERY_CHAT_ID', '')
    enabled = os.environ.get('TELEGRAM_DELIVERY_ENABLED', '')
    uat_url = os.environ.get('KAORI_UAT_URL', '')
    configured, reason = configuration_status(enabled=enabled, bot_token=bot_token, chat_id=chat_id)
    if not configured:
        print(f'SKIP — {reason}')
        return 0

    message = render_message(
        event=event,
        profile=args.profile,
        execution=args.execution,
        source_sha=args.source_sha,
        repository=args.repository,
        run_url=args.run_url,
        pr_number=args.pr_number,
        uat_url=uat_url,
    )
    delivered, detail = send_message(bot_token=bot_token, chat_id=chat_id, message=message)
    if not delivered:
        print(f'FAIL — {detail}', file=sys.stderr)
        return 1
    print(f'PASS — {detail} Event={event}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
