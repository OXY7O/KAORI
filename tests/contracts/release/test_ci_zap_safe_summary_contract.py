"""Contract tests for privacy-safe ZAP Runtime & DAST evidence publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci_zap_safe_summary import UnverifiedZapReport, main, render_summary

SHA = 'a' * 40
SENSITIVE = (
    'https://internal.example.invalid/login?token=secret',
    'Authorization: Bearer private-token',
    'Cookie: sessionid=private-session',
    "<script>alert('secret')</script>",
    'runtime:5000',
    '/auth/login',
)


def _alert(code: str | int, *, count: str = '2') -> dict:
    return {
        'riskcode': code,
        'count': count,
        'name': 'sensitive alert name ' + SENSITIVE[0],
        'alert': SENSITIVE[1],
        'desc': SENSITIVE[2],
        'instances': [
            {
                'uri': SENSITIVE[0],
                'requestHeader': SENSITIVE[1],
                'responseBody': SENSITIVE[3],
                'cookie': SENSITIVE[2],
                'attack': SENSITIVE[3],
            }
        ],
    }


def _report() -> dict:
    return {
        '@version': '2.17.0',
        'site': [
            {
                '@name': SENSITIVE[4],
                'alerts': [_alert('3'), _alert('1')],
            },
            {
                '@host': SENSITIVE[4],
                'alerts': [_alert(2), _alert('0'), _alert(2)],
            },
        ],
    }


def test_only_allowlisted_numeric_aggregates_appear_in_markdown() -> None:
    summary = render_summary(_report(), SHA)
    assert f'Committed source SHA: `{SHA}`' in summary
    assert '| High | 1 |' in summary
    assert '| Medium | 2 |' in summary
    assert '| Low | 1 |' in summary
    assert '| Informational | 1 |' in summary
    assert '| **Total** | **5** |' in summary
    assert 'Scanned site entries: **2**' in summary
    assert 'not** ZAP CLI FAIL/WARN/PASS counts' in summary
    assert 'not**' not in summary.split('These counts')[0]
    for value in SENSITIVE:
        assert value not in summary


@pytest.mark.parametrize(
    'payload',
    [
        {},
        [],
        {'site': []},
        {'site': [{'alerts': None}]},
        {'site': [{'alerts': []}, {'bad': 'missing alerts'}]},
        {'site': [{'alerts': [_alert('4')]}]},
        {'site': [{'alerts': [_alert('HIGH')]}]},
        {'site': [{'alerts': [_alert(True)]}]},
        {'site': [{'alerts': [42]}]},
    ],
)
def test_unverifiable_input_is_rejected_not_reported_as_zero(payload: object) -> None:
    with pytest.raises(UnverifiedZapReport):
        render_summary(payload, SHA)


def test_verified_empty_alert_list_does_not_claim_the_gate_passed() -> None:
    summary = render_summary({'site': [{'alerts': []}]}, SHA)
    assert '| **Total** | **0** |' in summary
    assert 'Actual gate result' in summary
    assert 'Code scanning' in summary


def test_source_sha_must_be_a_real_commit_digest() -> None:
    with pytest.raises(UnverifiedZapReport):
        render_summary(_report(), 'untrusted [link](https://example.invalid)')


def test_cli_writes_safe_summary_but_not_original_http_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / 'baseline.json'
    raw.write_text(json.dumps(_report()), encoding='utf-8')
    output = tmp_path / 'summary.md'
    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    sanitized = output.read_text(encoding='utf-8')
    for value in SENSITIVE:
        assert value not in sanitized
        assert value not in captured.out


def test_cli_does_not_echo_sensitive_content_when_report_is_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / 'baseline.json'
    raw.write_text('{"site": [' + SENSITIVE[0], encoding='utf-8')
    output = tmp_path / 'summary.md'
    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 2
    captured = capsys.readouterr()
    assert 'NOT VERIFIED' in captured.err
    assert not output.exists()
    for value in SENSITIVE:
        assert value not in captured.out + captured.err


def test_existing_zap_gate_remains_authoritative_and_summary_is_not_sarif() -> None:
    root = Path(__file__).resolve().parents[3]
    workflow = (root / '.github/workflows/quality.yml').read_text(encoding='utf-8')
    scanner = (root / '.github/ci/run-zap-baseline.sh').read_text(encoding='utf-8')
    runtime = (root / '.github/ci/run-runtime-validation.sh').read_text(encoding='utf-8')

    assert 'zap-baseline.py' in scanner
    assert '-I' in scanner
    assert '-r baseline.html' in scanner
    assert '-J baseline.json' in scanner
    assert 'bash .github/ci/run-zap-baseline.sh' in runtime
    assert "if: ${{ always() && matrix.gate == 'runtime' && steps.runtime_dast.outcome != 'skipped' }}" in workflow
    assert 'scripts/ci_zap_safe_summary.py' in workflow
    assert 'needs.validation-profile.outputs.source_sha' in workflow
    assert 'tmp/ci-artifacts/zap/sanitized-summary.md' in workflow
    assert 'name: Upload Sanitized ZAP Evidence' in workflow
    assert 'if-no-files-found: warn' in workflow
    assert 'Runtime and DAST results are deployment/security checks' in workflow
    assert 'category: kaori-dast-zap' not in workflow
    assert 'security-events: write' not in workflow


@pytest.mark.parametrize('changed_field', ['st_dev', 'st_ino', 'st_mode'])
def test_cli_rejects_descriptor_identity_or_mode_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_field: str
) -> None:
    """Do not publish evidence if the opened report's identity changes."""
    import os
    from types import SimpleNamespace

    raw = tmp_path / 'baseline.json'
    raw.write_text(json.dumps(_report()), encoding='utf-8')
    output = tmp_path / 'summary.md'
    output.write_text('stale verified evidence', encoding='utf-8')
    real_fstat = os.fstat
    calls = 0

    def drifting_fstat(fd: int) -> object:
        nonlocal calls
        original = real_fstat(fd)
        calls += 1
        fields = {
            key: getattr(original, key)
            for key in ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        }
        if calls == 2:
            fields[changed_field] += 1
        return SimpleNamespace(**fields)

    monkeypatch.setattr(os, 'fstat', drifting_fstat)
    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 2
    assert calls >= 2
    assert not output.exists()
    assert raw.exists()


def test_cli_rejects_excessive_json_object_members_without_publishing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A small raw report must not amplify into an unbounded JSON object."""
    from scripts.ci_zap_safe_summary import MAX_OBJECT_MEMBERS

    raw = tmp_path / 'baseline.json'
    # Include an otherwise valid site: the member limit must apply even when
    # excess fields would be ignored by the sanitized aggregate renderer.
    members = ','.join(f'"ignored_{index}":0' for index in range(MAX_OBJECT_MEMBERS))
    raw.write_text('{"site":[{"alerts":[]}],' + members + '}', encoding='utf-8')
    output = tmp_path / 'summary.md'
    output.write_text('stale verified evidence', encoding='utf-8')

    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert raw.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_cli_accepts_bounded_json_object_members(tmp_path: Path) -> None:
    from scripts.ci_zap_safe_summary import MAX_OBJECT_MEMBERS

    raw = tmp_path / 'baseline.json'
    members = ','.join(f'"ignored_{index}":0' for index in range(MAX_OBJECT_MEMBERS - 1))
    raw.write_text('{"site":[{"alerts":[]}],' + members + '}', encoding='utf-8')
    output = tmp_path / 'summary.md'

    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 0
    assert '| **Total** | **0** |' in output.read_text(encoding='utf-8')


def test_concurrent_cli_invocations_have_independent_json_object_budgets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two simultaneous reports must not consume a shared object counter."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    import scripts.ci_zap_safe_summary as zap_summary

    monkeypatch.setattr(zap_summary, 'MAX_JSON_OBJECTS', 3)
    barrier = Barrier(2)
    original_loads = zap_summary.json.loads

    def synchronized_loads(*args: object, **kwargs: object) -> object:
        barrier.wait(timeout=5)
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(zap_summary.json, 'loads', synchronized_loads)

    def run_one(index: int) -> int:
        raw = tmp_path / f'baseline-{index}.json'
        output = tmp_path / f'summary-{index}.md'
        raw.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
        return main(['--input', str(raw), '--output', str(output), '--source-sha', SHA])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run_one, range(2))) == [0, 0]
    assert all((tmp_path / f'summary-{i}.md').exists() for i in range(2))


def test_cli_rejects_in_place_temporary_evidence_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A same-inode temporary rewrite must not become published evidence."""

    raw = tmp_path / 'baseline.json'
    raw.write_text(json.dumps(_report()), encoding='utf-8')
    output = tmp_path / 'summary.md'
    original_stat = Path.stat
    tampered = False

    def tamper_before_stat(path: Path, *args: object, **kwargs: object) -> object:
        nonlocal tampered
        if path.name.startswith('.zap-summary-') and not tampered:
            tampered = True
            # Preserve inode and file type while changing the content and size.
            with path.open('a', encoding='utf-8') as stream:
                stream.write('UNTRUSTED TEMPORARY CONTENT')
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', tamper_before_stat)
    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 2
    assert tampered
    assert not output.exists()
    assert raw.exists()


def test_cli_rejects_symlinked_input_parent_without_publishing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O_NOFOLLOW on the final file must not permit a redirected parent."""
    real_dir = tmp_path / 'actual-reports'
    real_dir.mkdir()
    raw = real_dir / 'baseline.json'
    raw.write_text(json.dumps(_report()), encoding='utf-8')
    alias = tmp_path / 'report-alias'
    alias.symlink_to(real_dir, target_is_directory=True)
    output = tmp_path / 'summary.md'
    output.write_text('stale verified evidence', encoding='utf-8')

    assert main(['--input', str(alias / 'baseline.json'), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert raw.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_cli_rejects_input_parent_swapped_to_symlink_during_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A safe descriptor must not authorize a subsequently redirected pathname."""
    import scripts.ci_zap_safe_summary as zap_summary

    reports = tmp_path / 'reports'
    reports.mkdir()
    raw = reports / 'baseline.json'
    raw.write_text(json.dumps(_report()), encoding='utf-8')
    output = tmp_path / 'summary.md'
    output.write_text('stale evidence', encoding='utf-8')
    original_render = zap_summary.render_summary

    def swap_parent(payload: object, source_sha: str) -> str:
        result = original_render(payload, source_sha)
        reports.rename(tmp_path / 'moved-reports')
        reports.symlink_to(tmp_path / 'moved-reports', target_is_directory=True)
        return result

    monkeypatch.setattr(zap_summary, 'render_summary', swap_parent)
    assert main(['--input', str(raw), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert (tmp_path / 'moved-reports' / 'baseline.json').exists()
