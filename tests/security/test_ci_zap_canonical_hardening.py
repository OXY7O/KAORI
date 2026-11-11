"""Fail-closed canonical ZAP evidence regressions for #4400."""

import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'scripts' / 'ci_zap_safe_summary.py'
SPEC = importlib.util.spec_from_file_location('ci_zap_safe_summary', SOURCE)
zap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zap)
SHA = 'a' * 40


@pytest.mark.parametrize(
    'raw',
    [
        '{"site":[{"alerts":[{"riskcode":"3","riskcode":"0"}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","confidence":NaN}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","confidence":Infinity}]}]}',
        '[' * 1500 + '0' + ']' * 1500,
    ],
)
def test_ambiguous_nonfinite_or_deep_json_is_not_published(tmp_path, capsys, raw):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text(raw, encoding='utf-8')
    result = zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA])
    assert result == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_bounded_read_rejects_oversized_valid_json(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}],"padding":"' + 'x' * 100 + '"}', encoding='utf-8')
    monkeypatch.setattr(zap, 'MAX_REPORT_BYTES', 64)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_excessive_alert_families_fail_closed(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_FAMILIES', 1)
    payload = {'site': [{'alerts': [{'riskcode': '3'}, {'riskcode': '1'}]}]}
    with pytest.raises(zap.UnverifiedZapReport):
        zap.render_summary(payload, SHA)


def test_safe_multi_site_counts_never_echo_raw_urls():
    secret = 'https://private.example/path?token=never-publish'
    payload = {
        'site': [
            {'@name': secret, 'alerts': [{'riskcode': '3', 'uri': secret}]},
            {'@name': secret, 'alerts': [{'riskcode': 1, 'message': secret}]},
        ]
    }
    result = zap.render_summary(payload, SHA)
    assert '| High | 1 |' in result
    assert '| Low | 1 |' in result
    assert secret not in result


def test_excessive_scanned_sites_fail_closed(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_SITE_ENTRIES', 1)
    payload = {'site': [{'alerts': []}, {'alerts': []}]}
    with pytest.raises(zap.UnverifiedZapReport, match='Excessive scanned sites'):
        zap.render_summary(payload, SHA)


def test_site_limit_boundary_remains_valid(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_SITE_ENTRIES', 2)
    payload = {'site': [{'alerts': []}, {'alerts': []}]}
    summary = zap.render_summary(payload, SHA)
    assert 'Scanned site entries: **2**.' in summary


def test_invalid_report_removes_stale_summary_before_failure(tmp_path, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site": null}', encoding='utf-8')
    output.write_text('stale VERIFIED-looking evidence', encoding='utf-8')

    result = zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA])

    assert result == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_valid_report_replaces_stale_summary_without_leaking_it(tmp_path):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site": [{"alerts": []}]}', encoding='utf-8')
    output.write_text('old private payload', encoding='utf-8')

    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 0
    summary = output.read_text(encoding='utf-8')
    assert 'Committed source SHA' in summary
    assert 'old private payload' not in summary


@pytest.mark.parametrize('alias', ['same_path', 'symlink', 'hardlink'])
def test_output_alias_cannot_destroy_or_overwrite_raw_zap_evidence(tmp_path, capsys, alias):
    report = tmp_path / 'zap.json'
    raw = '{"site": [{"alerts": [{"riskcode": "3"}]}]}'
    report.write_text(raw, encoding='utf-8')
    output = tmp_path / 'summary.md'
    if alias == 'same_path':
        output = report
    elif alias == 'symlink':
        output.symlink_to(report)
    else:
        import os

        os.link(report, output)

    result = zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA])

    assert result == 2
    assert report.read_text(encoding='utf-8') == raw
    assert 'NOT VERIFIED' in capsys.readouterr().err
    if alias == 'symlink':
        assert output.is_symlink()


def test_overflow_float_in_ignored_json_field_fails_closed(tmp_path, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}],"unused":1e999}', encoding='utf-8')
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_atomic_publication_failure_leaves_no_partial_evidence(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site": [{"alerts": []}]}', encoding='utf-8')
    output.write_text('stale summary', encoding='utf-8')

    def fail_replace(_source, _destination):
        raise OSError('synthetic atomic publication failure')

    monkeypatch.setattr(zap.os, 'replace', fail_replace)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert not list(tmp_path.glob('.zap-summary-*.tmp'))
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_late_output_symlink_cannot_redirect_atomic_publication(tmp_path, monkeypatch):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    private = tmp_path / 'private.txt'
    report.write_text('{"site": [{"alerts": []}]}', encoding='utf-8')
    private.write_text('must stay private', encoding='utf-8')
    original_replace = zap.os.replace

    def inject_symlink_then_replace(source, destination):
        output.symlink_to(private)
        return original_replace(source, destination)

    monkeypatch.setattr(zap.os, 'replace', inject_symlink_then_replace)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 0
    assert not output.is_symlink()
    assert private.read_text(encoding='utf-8') == 'must stay private'
    assert 'Committed source SHA' in output.read_text(encoding='utf-8')
    assert not list(tmp_path.glob('.zap-summary-*.tmp'))

def test_alert_family_limit_is_cumulative_across_sites(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_FAMILIES', 2)
    payload = {'site': [
        {'alerts': [{'riskcode': '3'}]},
        {'alerts': [{'riskcode': '1'}, {'riskcode': '0'}]},
    ]}
    with pytest.raises(zap.UnverifiedZapReport, match='Excessive alert records'):
        zap.render_summary(payload, SHA)


def test_alert_family_limit_exact_boundary_across_sites(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_FAMILIES', 2)
    payload = {'site': [
        {'alerts': [{'riskcode': '3'}]},
        {'alerts': [{'riskcode': '1'}]},
    ]}
    summary = zap.render_summary(payload, SHA)
    assert '| **Total** | **2** |' in summary
