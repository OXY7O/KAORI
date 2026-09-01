from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_GITHUB_API: Final = 'https://api.github.com'
_FAILURE_RESULTS: Final = frozenset({'failure', 'timed_out', 'action_required'})
_RECEIPT_PREFIX: Final = 'kaori-telegram-quality-run-'
_LINKED_ISSUE_RE: Final = re.compile(r'(?im)\b(?:refs?|closes?|fixes?|resolves?)\s+#(?P<number>\d+)\b')
_MERGE_PR_RE: Final = re.compile(r'(?im)^Merge pull request #(?P<number>\d+)\b')


@dataclass(frozen=True, slots=True)
class DeliveryContext:
    issue_number: str = ''
    issue_title: str = ''
    issue_status: str = ''
    issue_url: str = ''
    pr_number: str = ''
    pr_title: str = ''
    pr_status: str = ''
    pr_url: str = ''
    test_guidance: str = ''


def github_api_get(*, path: str, token: str) -> Any:
    if not token.strip():
        raise RuntimeError('GitHub Actions read token is unavailable.')
    request = Request(
        f'{_GITHUB_API}{path}',
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
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise RuntimeError(f'GitHub Actions metadata lookup failed with HTTP {exc.code}.') from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError('GitHub Actions metadata lookup is unavailable or invalid.') from exc


def safe_repository(repository: str) -> str:
    return '/'.join(quote(part, safe='') for part in repository.split('/', 1))


def linked_issue_number(body: str) -> int | None:
    match = _LINKED_ISSUE_RE.search(body or '')
    return int(match.group('number')) if match is not None else None


def _pr_ref(pull_request: dict[str, Any], side: str) -> str:
    value = pull_request.get(side)
    return str(value.get('ref') or '') if isinstance(value, dict) else ''


def select_delivery_pr(
    pull_requests: list[dict[str, Any]],
    *,
    profile: str,
) -> dict[str, Any] | None:
    for pull_request in pull_requests:
        base_ref = _pr_ref(pull_request, 'base')
        head_ref = _pr_ref(pull_request, 'head')
        if profile in {'staging-integration', 'pr-integration'} and base_ref == 'kaori/staging':
            return pull_request
        if profile in {'post-promotion', 'promotion'} and base_ref == 'main' and head_ref == 'kaori/staging':
            return pull_request
    return None


def pr_run_profile(run: dict[str, Any]) -> str:
    pull_requests = run.get('pull_requests')
    if not isinstance(pull_requests, list) or not pull_requests:
        return 'full'
    pull_request = pull_requests[0]
    if not isinstance(pull_request, dict):
        return 'full'
    base_ref = _pr_ref(pull_request, 'base')
    head_ref = _pr_ref(pull_request, 'head')
    if base_ref == 'kaori/staging':
        return 'pr-integration'
    if base_ref == 'main' and head_ref == 'kaori/staging':
        return 'promotion'
    return 'full'


def select_unnotified_pr_failure(
    *,
    runs: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    receipts = {str(artifact.get('name') or '') for artifact in artifacts if isinstance(artifact, dict)}
    candidates = [
        run
        for run in runs
        if str(run.get('event') or '') == 'pull_request'
        and str(run.get('status') or '') == 'completed'
        and str(run.get('conclusion') or '') in _FAILURE_RESULTS
        and pr_run_profile(run) in {'pr-integration', 'promotion'}
        and f'{_RECEIPT_PREFIX}{run.get("id")}' not in receipts
    ]
    return max(candidates, key=lambda run: int(run.get('id') or 0)) if candidates else None


def fetch_recent_pr_quality_runs(*, repository: str, token: str) -> list[dict[str, Any]]:
    payload = github_api_get(
        path=(
            f'/repos/{safe_repository(repository)}/actions/workflows/quality.yml/'
            'runs?event=pull_request&status=completed&per_page=50'
        ),
        token=token,
    )
    runs = payload.get('workflow_runs') if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise RuntimeError('GitHub Actions PR workflow lookup returned an invalid payload.')
    return [run for run in runs if isinstance(run, dict)]


def fetch_notification_artifacts(*, repository: str, token: str) -> list[dict[str, Any]]:
    payload = github_api_get(
        path=f'/repos/{safe_repository(repository)}/actions/artifacts?per_page=100',
        token=token,
    )
    artifacts = payload.get('artifacts') if isinstance(payload, dict) else None
    if not isinstance(artifacts, list):
        raise RuntimeError('GitHub Actions artifact lookup returned an invalid payload.')
    return [artifact for artifact in artifacts if isinstance(artifact, dict)]


def _fetch_commit_pull_requests(
    *,
    repository: str,
    source_sha: str,
    token: str,
) -> list[dict[str, Any]]:
    payload = github_api_get(
        path=(f'/repos/{safe_repository(repository)}/commits/{quote(source_sha, safe="")}/pulls?per_page=100'),
        token=token,
    )
    if not isinstance(payload, list):
        raise RuntimeError('GitHub commit pull-request lookup returned an invalid payload.')
    return [pull_request for pull_request in payload if isinstance(pull_request, dict)]


def _fetch_pull_request(*, repository: str, pr_number: int, token: str) -> dict[str, Any]:
    payload = github_api_get(
        path=f'/repos/{safe_repository(repository)}/pulls/{pr_number}',
        token=token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError('GitHub pull-request lookup returned an invalid payload.')
    return payload


def _fetch_issue(*, repository: str, issue_number: int, token: str) -> dict[str, Any]:
    payload = github_api_get(
        path=f'/repos/{safe_repository(repository)}/issues/{issue_number}',
        token=token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError('GitHub issue lookup returned an invalid payload.')
    return payload


def _fetch_commit(*, repository: str, source_sha: str, token: str) -> dict[str, Any]:
    payload = github_api_get(
        path=f'/repos/{safe_repository(repository)}/commits/{quote(source_sha, safe="")}',
        token=token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError('GitHub commit lookup returned an invalid payload.')
    return payload


def _merge_commit_pr_number(commit: dict[str, Any]) -> int | None:
    commit_data = commit.get('commit')
    message = str(commit_data.get('message') or '') if isinstance(commit_data, dict) else ''
    match = _MERGE_PR_RE.search(message)
    return int(match.group('number')) if match is not None else None


def _pull_request_status(pull_request: dict[str, Any]) -> str:
    if pull_request.get('merged_at'):
        return 'Merged'
    if bool(pull_request.get('draft')):
        return 'Draft'
    return 'Closed' if str(pull_request.get('state') or '') == 'closed' else 'Ready'


def _uat_guidance(body: str) -> str:
    in_uat = False
    for raw_line in (body or '').splitlines():
        line = raw_line.strip()
        if line.startswith('## '):
            in_uat = line.lower() == '## uat'
            continue
        if in_uat and line.startswith('-'):
            guidance = re.sub(r'^-\s*(?:\[[ xX]\]\s*)?', '', line).strip()
            if guidance:
                return guidance
    return ''


def _resolve_pull_request(
    *,
    repository: str,
    source_sha: str,
    profile: str,
    token: str,
    pr_number: str,
) -> dict[str, Any] | None:
    if pr_number.strip().isdigit():
        return _fetch_pull_request(
            repository=repository,
            pr_number=int(pr_number),
            token=token,
        )
    selected = select_delivery_pr(
        _fetch_commit_pull_requests(
            repository=repository,
            source_sha=source_sha,
            token=token,
        ),
        profile=profile,
    )
    if selected is not None and int(selected.get('number') or 0):
        return _fetch_pull_request(
            repository=repository,
            pr_number=int(selected.get('number') or 0),
            token=token,
        )
    merge_pr_number = _merge_commit_pr_number(_fetch_commit(repository=repository, source_sha=source_sha, token=token))
    if merge_pr_number is None:
        return None
    return _fetch_pull_request(
        repository=repository,
        pr_number=merge_pr_number,
        token=token,
    )


def resolve_delivery_context(
    *,
    repository: str,
    source_sha: str,
    profile: str,
    token: str,
    pr_number: str = '',
) -> DeliveryContext:
    pull_request = _resolve_pull_request(
        repository=repository,
        source_sha=source_sha,
        profile=profile,
        token=token,
        pr_number=pr_number,
    )
    if pull_request is None:
        return DeliveryContext()

    issue_number = linked_issue_number(str(pull_request.get('body') or ''))
    issue = (
        _fetch_issue(repository=repository, issue_number=issue_number, token=token) if issue_number is not None else {}
    )
    return DeliveryContext(
        issue_number=str(issue_number or ''),
        issue_title=str(issue.get('title') or ''),
        issue_status=str(issue.get('state') or '').title(),
        issue_url=str(issue.get('html_url') or ''),
        pr_number=str(pull_request.get('number') or ''),
        pr_title=str(pull_request.get('title') or ''),
        pr_status=_pull_request_status(pull_request),
        pr_url=str(pull_request.get('html_url') or ''),
        test_guidance=_uat_guidance(str(issue.get('body') or '')),
    )
