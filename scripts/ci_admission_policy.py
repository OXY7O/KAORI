#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

PROFILE_VERSION = '3'
EVIDENCE_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
FULL_GATE_NAMES = (
    'Static, Architecture, and Governance',
    'Secrets, SAST, Dependencies, and Workflow Security',
    'Functional and Integration Tests',
    'Frontend Reproducibility',
    'Production Image, Container Security, Runtime, and DAST',
)
PROFILE_DISPLAY = {
    'full': 'Full Admission',
    'pr-integration': 'PR Integration',
    'staging-integration': 'Staging Integration',
    'promotion': 'Promotion',
    'post-promotion': 'Post-promotion',
}
AUTHORITY_PREFIXES = (
    '.github/workflows/',
    '.github/ci/',
    'requirements/',
    'tests/contracts/release/',
)
AUTHORITY_EXACT = (
    'scripts/ci_admission.py',
    'scripts/ci_admission_policy.py',
    'scripts/quality_gate.sh',
    'docs/engineering/KAORI_DELIVERY_WORKFLOW.md',
)


class ProfileDecision(NamedTuple):
    profile: str
    execution: str
    reason: str
    display_name: str


class ReuseDecision(NamedTuple):
    reusable: bool
    reason: str
    full_admission_run_id: int | None = None
    source_sha: str | None = None
    source_tree: str | None = None


def _is_authority_path(path: str) -> bool:
    normalized = path[2:] if path.startswith('./') else path
    return (
        normalized in AUTHORITY_EXACT
        or normalized.startswith(AUTHORITY_PREFIXES)
        or normalized.startswith('scripts/verify_')
        or normalized.startswith('Dockerfile')
        or normalized.startswith('docker-compose')
    )


def authority_fingerprint_from_entries(entries: Sequence[tuple[str, str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(f'profile-version:{PROFILE_VERSION}\0'.encode())
    for path, mode, blob_sha in sorted(entries):
        if not _is_authority_path(path):
            continue
        digest.update(path.encode())
        digest.update(b'\0')
        digest.update(mode.encode())
        digest.update(b'\0')
        digest.update(blob_sha.encode())
        digest.update(b'\0')
    return digest.hexdigest()


def compute_authority_fingerprint(root: Path | str = Path('.')) -> str:
    result = subprocess.run(
        ['git', 'ls-files', '-s', '-z'],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    entries: list[tuple[str, str, str]] = []
    authority_count = 0
    for record in result.stdout.split('\0'):
        if not record:
            continue
        metadata, path = record.split('\t', 1)
        mode, blob_sha, stage = metadata.split()
        if stage != '0':
            raise ValueError(f'Validation authority has an unmerged Git index entry: {path}')
        entries.append((path, mode, blob_sha))
        if _is_authority_path(path):
            authority_count += 1
    if authority_count == 0:
        raise ValueError('Validation authority fingerprint has no tracked authority files.')
    return authority_fingerprint_from_entries(entries)


def resolve_profile(
    *,
    event_name: str,
    ref: str,
    base_ref: str,
    head_ref: str,
    changed_paths: Sequence[str],
) -> ProfileDecision:
    del changed_paths
    if event_name == 'pull_request' and base_ref == 'kaori/staging':
        profile = 'pr-integration'
    elif event_name == 'pull_request' and base_ref == 'main' and head_ref == 'kaori/staging':
        profile = 'promotion'
    elif event_name == 'push' and ref == 'refs/heads/kaori/staging':
        profile = 'staging-integration'
    elif event_name == 'push' and ref == 'refs/heads/main':
        profile = 'post-promotion'
    else:
        profile = 'full'

    if profile == 'full':
        return ProfileDecision(
            profile,
            'full',
            'Source requires comprehensive validation at this governed boundary.',
            PROFILE_DISPLAY[profile],
        )
    return ProfileDecision(
        profile,
        'fast',
        'Eligible for immutable tree + validation-authority evidence reuse.',
        PROFILE_DISPLAY[profile],
    )


def _parse_evidence_timestamp(value: Any) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def evidence_reuse_decision(
    evidence: Mapping[str, Any],
    *,
    current_tree: str,
    current_authority_fingerprint: str,
    required_profile_version: str,
    now: datetime | None = None,
) -> ReuseDecision:
    if str(evidence.get('result', '')).upper() != 'PASS':
        return ReuseDecision(False, 'Full Admission evidence result is not PASS.')
    if str(evidence.get('profile', 'full')) != 'full':
        return ReuseDecision(False, 'Admission evidence profile is not Full Admission.')
    if str(evidence.get('profile_version', '')) != required_profile_version:
        return ReuseDecision(False, 'Validation profile version does not match current authority.')

    evidence_source_sha = str(evidence.get('source_sha', '')).strip()
    if not evidence_source_sha:
        return ReuseDecision(False, 'Admission evidence is missing source commit SHA.')
    if str(evidence.get('source_tree', '')) != current_tree:
        return ReuseDecision(False, 'Source tree does not match Admission evidence.')
    if str(evidence.get('authority_fingerprint', '')) != current_authority_fingerprint:
        return ReuseDecision(False, 'Validation authority fingerprint does not match Admission evidence.')

    created_at = _parse_evidence_timestamp(evidence.get('created_at'))
    if created_at is None:
        return ReuseDecision(False, 'Admission evidence is missing a valid timestamp.')
    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    age_seconds = (current_time - created_at).total_seconds()
    if age_seconds < -300:
        return ReuseDecision(False, 'Admission evidence timestamp is unexpectedly in the future.')
    if age_seconds > EVIDENCE_MAX_AGE_SECONDS:
        return ReuseDecision(False, 'Admission evidence is stale and must be refreshed.')

    gates = evidence.get('gates')
    if not isinstance(gates, Mapping):
        return ReuseDecision(False, 'Admission evidence does not contain required gate conclusions.')
    for gate in FULL_GATE_NAMES:
        conclusion = str(gates.get(gate, '')).lower()
        if conclusion != 'success':
            return ReuseDecision(False, f'{gate} is {conclusion or "missing"}; evidence is not reusable.')

    try:
        run_id = int(evidence.get('full_admission_run_id'))
    except (TypeError, ValueError):
        return ReuseDecision(False, 'Admission evidence is missing a valid Full Admission run ID.')
    if run_id <= 0:
        return ReuseDecision(False, 'Admission evidence Full Admission run ID is invalid.')

    try:
        run_attempt = int(evidence.get('run_attempt'))
    except (TypeError, ValueError):
        return ReuseDecision(False, 'Admission evidence is missing a valid run attempt.')
    if run_attempt <= 0:
        return ReuseDecision(False, 'Admission evidence run attempt is invalid.')

    workflow_ref = str(evidence.get('workflow_ref', '')).strip()
    if not workflow_ref:
        return ReuseDecision(False, 'Admission evidence is missing workflow identity.')
    if '.github/workflows/quality.yml@' not in workflow_ref:
        return ReuseDecision(False, 'Admission evidence workflow identity is not KAORI CI quality.yml.')

    return ReuseDecision(
        True,
        'Same immutable source tree and validation authority are reusable.',
        run_id,
        evidence_source_sha,
        current_tree,
    )


def staging_lineage_reuse_decision(
    *,
    parent_shas: Sequence[str],
    merge_tree: str,
    expected_staging_parent: str,
    admitted_head_sha: str,
    admitted_tree: str,
) -> ReuseDecision:
    if tuple(parent_shas) != (expected_staging_parent, admitted_head_sha):
        return ReuseDecision(False, 'Staging merge parents do not match the admitted lineage.')
    if merge_tree != admitted_tree:
        return ReuseDecision(False, 'Staging merge tree differs from the admitted source tree.')
    return ReuseDecision(
        True,
        'Staging parents and tree are equivalent to admitted lineage.',
        source_sha=admitted_head_sha,
        source_tree=admitted_tree,
    )


def promotion_lineage_reuse_decision(
    *,
    parent_shas: Sequence[str],
    merge_tree: str,
    expected_main_parent: str,
    accepted_staging_sha: str,
    accepted_tree: str,
) -> ReuseDecision:
    if tuple(parent_shas) != (expected_main_parent, accepted_staging_sha):
        return ReuseDecision(False, 'Promotion merge parents do not match the accepted staging lineage.')
    if merge_tree != accepted_tree:
        return ReuseDecision(False, 'Promotion tree differs from the UAT-accepted staging tree.')
    return ReuseDecision(
        True,
        'Promotion parents and tree preserve the accepted staging lineage.',
        source_sha=accepted_staging_sha,
        source_tree=accepted_tree,
    )


def _local_commit_metadata(sha: str) -> tuple[str, tuple[str, ...]]:
    tree = subprocess.run(
        ['git', 'show', '-s', '--format=%T', sha],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    parents_raw = subprocess.run(
        ['git', 'show', '-s', '--format=%P', sha],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return tree, tuple(parents_raw.split()) if parents_raw else ()


def transition_lineage_reuse_decision(
    *,
    profile: str,
    source_sha: str,
    source_tree: str,
    expected_before: str,
    expected_base: str,
    evidence_source_sha: str,
    evidence_source_tree: str,
) -> ReuseDecision:
    if not evidence_source_sha or not evidence_source_tree:
        return ReuseDecision(False, 'Transition lineage cannot be verified without exact Admission source identity.')
    if source_tree != evidence_source_tree:
        return ReuseDecision(False, 'Transition tree differs from the admitted evidence tree.')

    try:
        local_tree, parents = _local_commit_metadata(source_sha)
    except (OSError, subprocess.CalledProcessError) as exc:
        return ReuseDecision(False, f'Transition lineage lookup failed closed: {exc}')
    if local_tree != source_tree:
        return ReuseDecision(False, 'Checked-out source tree differs from the routed source tree.')

    if profile == 'pr-integration':
        if not expected_base:
            return ReuseDecision(False, 'PR Integration is missing the expected staging base authority.')
        if source_sha != evidence_source_sha:
            return ReuseDecision(False, 'PR head does not match the admitted source SHA.')
        return ReuseDecision(
            True,
            'PR head and tree match admitted Full Admission evidence.',
            source_sha=source_sha,
            source_tree=source_tree,
        )

    if profile == 'staging-integration':
        if not expected_before:
            return ReuseDecision(False, 'Staging Integration is missing the previous staging authority.')
        return staging_lineage_reuse_decision(
            parent_shas=parents,
            merge_tree=source_tree,
            expected_staging_parent=expected_before,
            admitted_head_sha=evidence_source_sha,
            admitted_tree=evidence_source_tree,
        )

    if profile == 'promotion':
        if not expected_base:
            return ReuseDecision(False, 'Promotion is missing the expected main base authority.')
        if source_sha == evidence_source_sha:
            return ReuseDecision(
                True,
                'Promotion head is the exact admitted staging source.',
                source_sha=source_sha,
                source_tree=source_tree,
            )
        if len(parents) >= 2 and parents[1] == evidence_source_sha:
            return ReuseDecision(
                True,
                'Promotion staging head preserves the admitted merge lineage.',
                source_sha=source_sha,
                source_tree=source_tree,
            )
        return ReuseDecision(False, 'Promotion staging head does not preserve the admitted source lineage.')

    if profile == 'post-promotion':
        if not expected_before:
            return ReuseDecision(False, 'Post-promotion is missing the previous main authority.')
        if len(parents) != 2 or parents[0] != expected_before:
            return ReuseDecision(False, 'Post-promotion main parents do not match the expected promotion lineage.')
        accepted_staging_sha = parents[1]
        try:
            accepted_tree, accepted_parents = _local_commit_metadata(accepted_staging_sha)
        except (OSError, subprocess.CalledProcessError) as exc:
            return ReuseDecision(False, f'Accepted staging lineage lookup failed closed: {exc}')
        if accepted_tree != source_tree:
            return ReuseDecision(False, 'Post-promotion tree differs from the accepted staging tree.')
        if accepted_staging_sha != evidence_source_sha and evidence_source_sha not in accepted_parents:
            return ReuseDecision(False, 'Accepted staging lineage does not preserve the admitted source SHA.')
        return ReuseDecision(
            True,
            'Post-promotion main tree preserves the accepted staging and admitted source lineage.',
            source_sha=accepted_staging_sha,
            source_tree=accepted_tree,
        )

    return ReuseDecision(False, f'Unsupported fast validation profile for lineage verification: {profile}')


def render_operator_summary(
    *,
    result: str,
    profile: str,
    commit_sha: str,
    tree_sha: str,
    evidence: str,
    fresh_checks: Sequence[str],
    reused_coverage: Sequence[str],
    duration: str,
    first_failure: str | None,
    next_action: str,
    coverage_summary: str | None = None,
) -> str:
    normalized = result.upper()
    if normalized not in {'PASS', 'FAIL', 'SKIP', 'REUSED', 'FALLBACK'}:
        raise ValueError(f'Unsupported KAORI result vocabulary: {result}')
    lines = [
        f'## KAORI CI — {profile}',
        '',
        f'**Result:** {normalized}',
        f'**Profile:** {profile}',
        f'**Commit SHA:** `{commit_sha}`',
        f'**Tree SHA:** `{tree_sha}`',
        f'**Evidence:** {evidence}',
        f'**Duration:** {duration}',
        f'**Coverage summary:** {coverage_summary or "See grouped gate results below."}',
        f'**Fresh checks:** {", ".join(fresh_checks) if fresh_checks else "None"}',
        f'**Reused checks:** {", ".join(reused_coverage) if reused_coverage else "None"}',
    ]
    if first_failure and first_failure.strip().lower() not in {'none', 'n/a'}:
        lines.append(f'**First actionable failure:** {first_failure}')
    lines.extend((f'**Next action:** {next_action}', ''))
    return '\n'.join(lines)


def build_full_evidence(
    *,
    source_sha: str,
    source_tree: str,
    authority_fingerprint: str,
    run_id: int,
    run_attempt: int,
    workflow_ref: str,
    gates: Mapping[str, str],
) -> dict[str, Any]:
    return {
        'result': 'PASS',
        'profile': 'full',
        'profile_version': PROFILE_VERSION,
        'created_at': datetime.now(UTC).isoformat(),
        'source_sha': source_sha,
        'source_tree': source_tree,
        'authority_fingerprint': authority_fingerprint,
        'full_admission_run_id': run_id,
        'run_attempt': run_attempt,
        'workflow_ref': workflow_ref,
        'gates': dict(gates),
    }


def _validated_github_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'api.github.com':
        raise ValueError('KAORI CI Admission only permits HTTPS requests to api.github.com.')
    if parsed.username or parsed.password:
        raise ValueError('KAORI CI Admission does not permit credentials embedded in request URLs.')
    return parsed.geturl()


class _GitHubArtifactRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        target = urllib.parse.urlparse(newurl)
        if target.scheme != 'https':
            raise ValueError('KAORI CI Admission artifact redirects must remain HTTPS.')

        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None

        source_host = urllib.parse.urlparse(req.full_url).hostname
        if target.hostname != source_host:
            redirected.remove_header('Authorization')
        return redirected


def _github_request(url: str, token: str, *, binary: bool = False) -> Any:
    request = urllib.request.Request(
        _validated_github_url(url),
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'KAORI-CI-Admission',
        },
    )
    if binary:
        opener = urllib.request.build_opener(_GitHubArtifactRedirectHandler())
        with opener.open(request, timeout=60) as response:  # nosec B310
            return response.read()
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
        return json.load(response)


def _commit_metadata(repository: str, token: str, sha: str) -> tuple[str, tuple[str, ...]]:
    payload = _github_request(f'https://api.github.com/repos/{repository}/commits/{sha}', token)
    return str(payload['commit']['tree']['sha']), tuple(str(parent['sha']) for parent in payload.get('parents', ()))


def _candidate_lineage(repository: str, token: str, start_sha: str, max_depth: int = 4) -> list[tuple[str, str]]:
    queue: list[tuple[str, int]] = [(start_sha, 0)]
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []
    while queue:
        sha, depth = queue.pop(0)
        if sha in seen or depth > max_depth:
            continue
        seen.add(sha)
        tree, parents = _commit_metadata(repository, token, sha)
        candidates.append((sha, tree))
        ordered = list(parents[1:2]) + list(parents[:1]) + list(parents[2:])
        queue.extend((parent, depth + 1) for parent in ordered)
    return candidates


def find_remote_full_evidence(
    *,
    repository: str,
    token: str,
    workflow: str,
    start_sha: str,
    current_tree: str,
    current_authority_fingerprint: str | None = None,
) -> ReuseDecision:
    try:
        fingerprint = current_authority_fingerprint or compute_authority_fingerprint()
        encoded_workflow = urllib.parse.quote(workflow, safe='')
        for candidate_sha, candidate_tree in _candidate_lineage(repository, token, start_sha):
            if candidate_tree != current_tree:
                continue
            query = urllib.parse.urlencode({'head_sha': candidate_sha, 'status': 'success', 'per_page': 20})
            runs = _github_request(
                f'https://api.github.com/repos/{repository}/actions/workflows/{encoded_workflow}/runs?{query}', token
            ).get('workflow_runs', [])
            for run in runs:
                run_id = int(run['id'])
                artifacts = _github_request(
                    f'https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts', token
                ).get('artifacts', [])
                for artifact in artifacts:
                    if not str(artifact.get('name', '')).startswith('kaori-full-admission-'):
                        continue
                    if bool(artifact.get('expired')):
                        continue
                    archive = _github_request(str(artifact['archive_download_url']), token, binary=True)
                    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                        if 'admission-evidence.json' not in bundle.namelist():
                            continue
                        evidence = json.loads(bundle.read('admission-evidence.json').decode('utf-8'))
                    if str(evidence.get('source_sha', '')) != candidate_sha:
                        continue
                    decision = evidence_reuse_decision(
                        evidence,
                        current_tree=current_tree,
                        current_authority_fingerprint=fingerprint,
                        required_profile_version=PROFILE_VERSION,
                    )
                    if decision.reusable:
                        return decision
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        return ReuseDecision(False, f'Admission evidence lookup failed closed: {type(exc).__name__}: {exc}')
    return ReuseDecision(False, 'No reusable Full Admission evidence was found for this tree and authority.')


def _write_output(values: Mapping[str, str]) -> None:
    payload = ''.join(f'{key}={value}\n' for key, value in values.items())
    output_path = os.environ.get('GITHUB_OUTPUT')
    if output_path:
        with Path(output_path).open('a', encoding='utf-8') as stream:
            stream.write(payload)
    else:
        sys.stdout.write(payload)


def _route(args: argparse.Namespace) -> int:
    changed = (
        tuple(Path(args.changed_paths_file).read_text(encoding='utf-8').splitlines()) if args.changed_paths_file else ()
    )
    decision = resolve_profile(
        event_name=args.event_name,
        ref=args.ref,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_paths=changed,
    )
    _write_output(
        {
            'profile': decision.profile,
            'execution': decision.execution,
            'reason': decision.reason.replace('\n', ' '),
            'display_profile': decision.display_name,
        }
    )
    return 0


def _find_evidence(args: argparse.Namespace) -> int:
    decision = find_remote_full_evidence(
        repository=args.repository,
        token=args.token,
        workflow=args.workflow,
        start_sha=args.start_sha,
        current_tree=args.current_tree,
    )
    _write_output(
        {
            'reusable': 'true' if decision.reusable else 'false',
            'evidence_run_id': str(decision.full_admission_run_id or ''),
            'evidence_source_sha': decision.source_sha or '',
            'evidence_source_tree': decision.source_tree or '',
            'evidence_reason': decision.reason.replace('\n', ' '),
        }
    )
    return 0


def _verify_lineage(args: argparse.Namespace) -> int:
    decision = transition_lineage_reuse_decision(
        profile=args.profile,
        source_sha=args.source_sha,
        source_tree=args.source_tree,
        expected_before=args.expected_before,
        expected_base=args.expected_base,
        evidence_source_sha=args.evidence_source_sha,
        evidence_source_tree=args.evidence_source_tree,
    )
    _write_output(
        {
            'lineage_reusable': 'true' if decision.reusable else 'false',
            'lineage_reason': decision.reason.replace('\n', ' '),
        }
    )
    return 0


def _write_evidence(args: argparse.Namespace) -> int:
    gates = {
        'Static, Architecture, and Governance': args.static_quality,
        'Secrets, SAST, Dependencies, and Workflow Security': args.static_security,
        'Functional and Integration Tests': args.functional_tests,
        'Frontend Reproducibility': args.frontend,
        'Production Image, Container Security, Runtime, and DAST': args.production_runtime,
    }
    if any(value != 'success' for value in gates.values()):
        raise SystemExit('Cannot publish Full Admission evidence unless every comprehensive gate succeeded.')
    payload = build_full_evidence(
        source_sha=args.source_sha,
        source_tree=args.source_tree,
        authority_fingerprint=compute_authority_fingerprint(),
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        workflow_ref=args.workflow_ref,
        gates=gates,
    )
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


def _summary(args: argparse.Namespace) -> int:
    summary = render_operator_summary(
        result=args.result,
        profile=args.profile,
        commit_sha=args.commit_sha,
        tree_sha=args.tree_sha,
        evidence=args.evidence,
        fresh_checks=tuple(filter(None, (part.strip() for part in args.fresh_checks.split('|')))),
        reused_coverage=tuple(filter(None, (part.strip() for part in args.reused_checks.split('|')))),
        duration=args.duration,
        first_failure=args.first_failure,
        next_action=args.next_action,
        coverage_summary=args.coverage_summary,
    )
    if args.output:
        with Path(args.output).open('a', encoding='utf-8') as stream:
            stream.write(summary)
    else:
        print(summary, end='')
    return 0


def _authority_fingerprint_command(args: argparse.Namespace) -> int:
    del args
    print(compute_authority_fingerprint())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='KAORI progressive CI Admission policy helper')
    sub = parser.add_subparsers(dest='command', required=True)

    route = sub.add_parser('route')
    route.add_argument('--event-name', required=True)
    route.add_argument('--ref', required=True)
    route.add_argument('--base-ref', default='')
    route.add_argument('--head-ref', default='')
    route.add_argument('--changed-paths-file')
    route.set_defaults(func=_route)

    evidence = sub.add_parser('find-evidence')
    evidence.add_argument('--repository', required=True)
    evidence.add_argument('--token', required=True)
    evidence.add_argument('--workflow', default='quality.yml')
    evidence.add_argument('--start-sha', required=True)
    evidence.add_argument('--current-tree', required=True)
    evidence.set_defaults(func=_find_evidence)

    lineage = sub.add_parser('verify-lineage')
    lineage.add_argument('--profile', required=True)
    lineage.add_argument('--source-sha', required=True)
    lineage.add_argument('--source-tree', required=True)
    lineage.add_argument('--expected-before', default='')
    lineage.add_argument('--expected-base', default='')
    lineage.add_argument('--evidence-source-sha', required=True)
    lineage.add_argument('--evidence-source-tree', required=True)
    lineage.set_defaults(func=_verify_lineage)

    writer = sub.add_parser('write-evidence')
    writer.add_argument('--source-sha', required=True)
    writer.add_argument('--source-tree', required=True)
    writer.add_argument('--run-id', type=int, required=True)
    writer.add_argument('--run-attempt', type=int, required=True)
    writer.add_argument('--workflow-ref', required=True)
    writer.add_argument('--static-quality', required=True)
    writer.add_argument('--static-security', required=True)
    writer.add_argument('--functional-tests', required=True)
    writer.add_argument('--frontend', required=True)
    writer.add_argument('--production-runtime', required=True)
    writer.add_argument('--output', default='admission-evidence.json')
    writer.set_defaults(func=_write_evidence)

    summary = sub.add_parser('summary')
    summary.add_argument('--result', required=True)
    summary.add_argument('--profile', required=True)
    summary.add_argument('--commit-sha', required=True)
    summary.add_argument('--tree-sha', required=True)
    summary.add_argument('--evidence', required=True)
    summary.add_argument('--duration', required=True)
    summary.add_argument('--coverage-summary', default='')
    summary.add_argument('--fresh-checks', default='')
    summary.add_argument('--reused-checks', default='')
    summary.add_argument('--first-failure')
    summary.add_argument('--next-action', required=True)
    summary.add_argument('--output')
    summary.set_defaults(func=_summary)

    fingerprint = sub.add_parser('authority-fingerprint')
    fingerprint.set_defaults(func=_authority_fingerprint_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
