"""Fail-closed tests for sanitized publication history preflight (#4212)."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[3] / 'scripts' / 'publication_history_coverage.py'
spec = importlib.util.spec_from_file_location('publication_history_coverage', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def runner_with(outputs, codes=None):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        index = len(calls) - 1
        return SimpleNamespace(stdout=outputs[index], returncode=(codes or [0, 0, 0])[index])

    return run, calls


def test_complete_local_metadata_never_grants_clearance():
    runner, calls = runner_with(['false\n', '17\n', 'refs/heads/staging\nrefs/tags/v1\n'])
    result = module.inventory(runner)
    assert result['assessment'] == 'INCOMPLETE'
    assert result['history_metadata_access'] == 'READ'
    assert result['commit_count'] == 17
    assert result['local_ref_count'] == 2
    assert result['shallow'] is False
    assert all(call[1]['timeout'] == 30 for call in calls)


def test_shallow_checkout_is_reported_not_cleared():
    runner, _ = runner_with(['true\n', '3\n', 'refs/heads/staging\n'])
    assert module.inventory(runner)['shallow'] is True


def test_missing_refs_fail_closed():
    runner, _ = runner_with(['false\n', '3\n', ''])
    result = module.inventory(runner)
    assert result['history_metadata_access'] == 'FAILED_OR_INCOMPLETE'
    assert result['commit_count'] is None


def test_command_failure_does_not_expose_stderr():
    runner, _ = runner_with(['secret-value', '', ''], [1, 0, 0])
    result = module.inventory(runner)
    assert result['assessment'] == 'INCOMPLETE'
    assert 'secret-value' not in str(result)


def test_invalid_metadata_fails_closed():
    runner, _ = runner_with(['false\n', 'not-a-number\n', 'refs/heads/staging\n'])
    assert module.inventory(runner)['history_metadata_access'] == 'FAILED_OR_INCOMPLETE'


def test_duplicate_refs_fail_closed():
    runner, _ = runner_with(['false\n', '2\n', 'refs/heads/a\nrefs/heads/a\n'])
    assert module.inventory(runner)['history_metadata_access'] == 'FAILED_OR_INCOMPLETE'
