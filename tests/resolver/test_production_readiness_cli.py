from __future__ import annotations

import io
import json

from app.resolver.production_readiness import REQUIRED_CHECKS
from scripts.verify_resolver_production_readiness import run


def passing_results() -> dict[str, bool]:
    return {name: True for name in REQUIRED_CHECKS}


def test_cli_returns_zero_for_complete_evidence(tmp_path) -> None:
    evidence = tmp_path / 'evidence.json'
    evidence.write_text(json.dumps(passing_results()), encoding='utf-8')
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run([str(evidence), '--rollout-stage', 'canary'], stdout=stdout, stderr=stderr)

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload['ready'] is True
    assert payload['rollout_stage'] == 'canary'
    assert payload['failed_checks'] == []
    assert payload['evidence_hash']
    assert stderr.getvalue() == ''


def test_cli_returns_one_when_required_check_fails(tmp_path) -> None:
    results = passing_results()
    results['worker_loss_recovery'] = False
    evidence = tmp_path / 'evidence.json'
    evidence.write_text(json.dumps(results), encoding='utf-8')
    stdout = io.StringIO()

    exit_code = run([str(evidence)], stdout=stdout, stderr=io.StringIO())

    payload = json.loads(stdout.getvalue())
    assert exit_code == 1
    assert payload['ready'] is False
    assert payload['failed_checks'] == ['worker_loss_recovery']


def test_cli_returns_two_for_invalid_json(tmp_path) -> None:
    evidence = tmp_path / 'evidence.json'
    evidence.write_text('{invalid', encoding='utf-8')
    stderr = io.StringIO()

    exit_code = run([str(evidence)], stdout=io.StringIO(), stderr=stderr)

    payload = json.loads(stderr.getvalue())
    assert exit_code == 2
    assert 'invalid JSON' in payload['error']


def test_cli_rejects_non_object_json(tmp_path) -> None:
    evidence = tmp_path / 'evidence.json'
    evidence.write_text('[]', encoding='utf-8')
    stderr = io.StringIO()

    exit_code = run([str(evidence)], stdout=io.StringIO(), stderr=stderr)

    payload = json.loads(stderr.getvalue())
    assert exit_code == 2
    assert payload['error'] == 'Evidence JSON root must be an object keyed by readiness check name.'
