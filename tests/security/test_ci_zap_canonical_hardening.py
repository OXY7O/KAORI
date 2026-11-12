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
    payload = {
        'site': [
            {'alerts': [{'riskcode': '3'}]},
            {'alerts': [{'riskcode': '1'}, {'riskcode': '0'}]},
        ]
    }
    with pytest.raises(zap.UnverifiedZapReport, match='Excessive alert records'):
        zap.render_summary(payload, SHA)


def test_alert_family_limit_exact_boundary_across_sites(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_FAMILIES', 2)
    payload = {
        'site': [
            {'alerts': [{'riskcode': '3'}]},
            {'alerts': [{'riskcode': '1'}]},
        ]
    }
    summary = zap.render_summary(payload, SHA)
    assert '| **Total** | **2** |' in summary


def test_cumulative_instance_limit_rejects_multiple_sites(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_INSTANCES', 2)
    payload = {
        'site': [
            {'alerts': [{'riskcode': '3', 'instances': [{'uri': 'private'}]}]},
            {'alerts': [{'riskcode': '1', 'instances': [{}, {}]}]},
        ]
    }
    with pytest.raises(zap.UnverifiedZapReport, match='Excessive alert instances'):
        zap.render_summary(payload, SHA)


def test_instance_limit_boundary_does_not_publish_instance_details(monkeypatch):
    monkeypatch.setattr(zap, 'MAX_ALERT_INSTANCES', 2)
    secret = 'https://private.example/?token=do-not-publish'
    payload = {'site': [{'alerts': [{'riskcode': '3', 'instances': [{'uri': secret}, {}]}]}]}
    summary = zap.render_summary(payload, SHA)
    assert '| High | 1 |' in summary
    assert secret not in summary


def test_malformed_instances_fail_closed():
    payload = {'site': [{'alerts': [{'riskcode': '3', 'instances': 'not-a-list'}]}]}
    with pytest.raises(zap.UnverifiedZapReport, match='Invalid alert instances'):
        zap.render_summary(payload, SHA)


@pytest.mark.parametrize('invalid_instance', [None, 'sensitive', 7, ['nested']])
def test_malformed_instance_entry_fails_closed_without_echoing_private_data(tmp_path, capsys, invalid_instance):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text(
        __import__('json').dumps({'site': [{'alerts': [{'riskcode': '3', 'instances': [invalid_instance]}]}]}),
        encoding='utf-8',
    )
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    captured = capsys.readouterr()
    assert 'NOT VERIFIED' in captured.err
    assert 'sensitive' not in captured.err


def test_valid_instance_objects_remain_accepted_without_publishing_details():
    secret = 'https://private.example/?token=never-echo'
    payload = {'site': [{'alerts': [{'riskcode': '3', 'instances': [{'uri': secret}, {}]}]}]}
    summary = zap.render_summary(payload, SHA)
    assert '| High | 1 |' in summary
    assert secret not in summary


def test_instance_total_is_numeric_and_excludes_private_fields():
    secret = 'https://private.example/path?token=do-not-emit'
    payload = {
        'site': [
            {'alerts': [{'riskcode': '3', 'instances': [{'uri': secret}, {}]}]},
            {'alerts': [{'riskcode': '1', 'instances': [{'message': secret}]}]},
        ]
    }
    summary = zap.render_summary(payload, SHA)
    assert 'Alert instance entries: **3**.' in summary
    assert 'Scanned site entries: **2**.' in summary
    assert secret not in summary


def test_missing_instance_arrays_do_not_claim_verified_zero():
    payload = {'site': [{'alerts': [{'riskcode': '3'}]}]}
    summary = zap.render_summary(payload, SHA)
    assert 'Alert instance entries: **NOT VERIFIED** (missing instance arrays).' in summary
    assert '| High | 1 |' in summary
    assert 'proof of complete application security' in summary


def test_mixed_present_and_missing_instances_do_not_claim_partial_total():
    payload = {
        'site': [
            {
                'alerts': [
                    {'riskcode': '3', 'instances': [{}, {}]},
                    {'riskcode': '1'},
                ]
            }
        ]
    }
    summary = zap.render_summary(payload, SHA)
    assert 'Alert instance entries: **NOT VERIFIED**' in summary
    assert 'Alert instance entries: **2**.' not in summary
    assert '| **Total** | **2** |' in summary


def test_explicit_empty_instance_arrays_report_verified_zero():
    payload = {'site': [{'alerts': [{'riskcode': '3', 'instances': []}]}]}
    summary = zap.render_summary(payload, SHA)
    assert 'Alert instance entries: **0**.' in summary
    assert '| High | 1 |' in summary


@pytest.mark.parametrize('riskcode', [True, False, 1.0, -1, 4, '04', None])
def test_noncanonical_riskcode_never_claims_verified_evidence(riskcode):
    payload = {'site': [{'alerts': [{'riskcode': riskcode, 'instances': []}]}]}
    with pytest.raises(zap.UnverifiedZapReport, match='Invalid risk category'):
        zap.render_summary(payload, SHA)


def test_fifo_report_is_rejected_before_blocking_read(tmp_path, monkeypatch, capsys):
    import os

    if not hasattr(os, 'mkfifo'):
        pytest.skip('FIFO not supported on this platform')
    report = tmp_path / 'zap.fifo'
    output = tmp_path / 'summary.md'
    os.mkfifo(report)
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    original_open = os.open

    def inspect_nonblocking_open(path, flags, *args, **kwargs):
        if path == report:
            assert flags & os.O_NONBLOCK
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, 'open', inspect_nonblocking_open)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_swapped_fifo_is_rejected_by_open_descriptor(tmp_path, monkeypatch, capsys):
    import os

    if not hasattr(os, 'mkfifo'):
        pytest.skip('FIFO not supported on this platform')
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    original_open = os.open

    def swap_before_open(path, flags, *args, **kwargs):
        if path == report:
            report.unlink()
            os.mkfifo(report)
            assert flags & os.O_NONBLOCK
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, 'open', swap_before_open)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_failed_fdopen_closes_raw_report_descriptor(tmp_path, monkeypatch, capsys):
    import os

    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale evidence', encoding='utf-8')
    original_open = os.open
    original_fdopen = os.fdopen
    opened = []

    def record_open(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if path == report:
            opened.append(descriptor)
        return descriptor

    def fail_report_wrap(descriptor, *args, **kwargs):
        if descriptor in opened:
            raise OSError('synthetic stream wrapping failure')
        return original_fdopen(descriptor, *args, **kwargs)

    monkeypatch.setattr(os, 'open', record_open)
    monkeypatch.setattr(os, 'fdopen', fail_report_wrap)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_opened_regular_file_size_is_checked_before_read(tmp_path, monkeypatch, capsys):
    import os

    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    original_fstat = os.fstat

    def oversized_descriptor_stat(descriptor):
        actual = original_fstat(descriptor)
        if actual.st_size == report.stat().st_size:
            # Simulate a filesystem reporting an oversized opened regular file.
            values = list(actual)
            values[6] = zap.MAX_REPORT_BYTES + 1
            return os.stat_result(values)
        return actual

    monkeypatch.setattr(zap.os, 'fstat', oversized_descriptor_stat)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_symlinked_output_directory_cannot_redirect_evidence(tmp_path, capsys):
    report = tmp_path / 'zap.json'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    outside = tmp_path / 'outside'
    outside.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(outside, target_is_directory=True)
    output = alias / 'summary.md'

    result = zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA])

    assert result == 2
    assert not output.exists()
    assert not (outside / 'summary.md').exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_invalid_source_sha_clears_stale_evidence_without_opening_raw_report(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    original_open = zap.os.open
    opened_report = []

    def reject_report_open(path, flags, *args, **kwargs):
        if path == report:
            opened_report.append(path)
            raise AssertionError('Invalid identity must fail before raw report access')
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(zap.os, 'open', reject_report_open)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', 'invalid']) == 2
    assert not opened_report
    assert not output.exists()
    assert report.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_report_mutated_during_read_is_not_published(tmp_path, monkeypatch, capsys):
    import os

    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    original_fstat = os.fstat
    calls = 0

    def changed_descriptor_stat(descriptor):
        nonlocal calls
        actual = original_fstat(descriptor)
        if actual.st_size == report.stat().st_size:
            calls += 1
            if calls == 2:
                values = list(actual)
                values[6] += 1
                return os.stat_result(values)
        return actual

    monkeypatch.setattr(zap.os, 'fstat', changed_descriptor_stat)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert calls == 2
    assert not output.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_unchanged_descriptor_remains_publishable(tmp_path):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 0
    assert 'Scanned site entries: **1**.' in output.read_text(encoding='utf-8')


def test_missing_nofollow_support_fails_closed_before_raw_report_open(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    opened_report = []
    original_open = zap.os.open

    def track_open(path, flags, *args, **kwargs):
        if path == report:
            opened_report.append(path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(zap.os, 'open', track_open)
    monkeypatch.delattr(zap.os, 'O_NOFOLLOW', raising=False)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not opened_report
    assert not output.exists()
    assert report.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_short_read_with_stable_descriptor_metadata_is_not_verified(tmp_path, monkeypatch, capsys):
    import os

    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    original_fstat = os.fstat
    report_size = report.stat().st_size

    def stable_but_incomplete_descriptor_stat(descriptor):
        actual = original_fstat(descriptor)
        if actual.st_size == report_size:
            values = list(actual)
            values[6] += 1
            return os.stat_result(values)
        return actual

    monkeypatch.setattr(zap.os, 'fstat', stable_but_incomplete_descriptor_stat)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert report.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_output_parent_swapped_to_symlink_during_parse_fails_closed(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    safe_parent = tmp_path / 'safe'
    safe_parent.mkdir()
    output = safe_parent / 'summary.md'
    output.write_text('stale summary', encoding='utf-8')
    outside = tmp_path / 'outside'
    outside.mkdir()
    original_render = zap.render_summary

    def swap_parent_during_parse(payload, source_sha):
        summary = original_render(payload, source_sha)
        safe_parent.rename(tmp_path / 'old-safe')
        safe_parent.symlink_to(outside, target_is_directory=True)
        return summary

    monkeypatch.setattr(zap, 'render_summary', swap_parent_during_parse)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not (outside / 'summary.md').exists()
    assert not list(outside.glob('.zap-summary-*.tmp'))
    assert not (tmp_path / 'old-safe' / 'summary.md').exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_missing_nonblocking_support_fails_closed_before_raw_report_open(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    output = tmp_path / 'summary.md'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    output.write_text('stale verified-looking evidence', encoding='utf-8')
    opened_report = []
    original_open = zap.os.open

    def track_open(path, flags, *args, **kwargs):
        if path == report:
            opened_report.append(path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(zap.os, 'open', track_open)
    monkeypatch.delattr(zap.os, 'O_NONBLOCK', raising=False)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not opened_report
    assert not output.exists()
    assert report.exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err


def test_output_parent_replaced_by_regular_directory_during_parse_fails_closed(tmp_path, monkeypatch, capsys):
    report = tmp_path / 'zap.json'
    report.write_text('{"site":[{"alerts":[]}]}', encoding='utf-8')
    parent = tmp_path / 'evidence'
    parent.mkdir()
    output = parent / 'summary.md'
    output.write_text('stale evidence', encoding='utf-8')
    replacement = tmp_path / 'replacement'
    replacement.mkdir()
    original_render = zap.render_summary

    def replace_parent_during_parse(payload, source_sha):
        summary = original_render(payload, source_sha)
        parent.rename(tmp_path / 'previous-evidence')
        replacement.rename(parent)
        return summary

    monkeypatch.setattr(zap, 'render_summary', replace_parent_during_parse)
    assert zap.main(['--input', str(report), '--output', str(output), '--source-sha', SHA]) == 2
    assert not output.exists()
    assert not list(parent.glob('.zap-summary-*.tmp'))
    assert not (tmp_path / 'previous-evidence' / 'summary.md').exists()
    assert 'NOT VERIFIED' in capsys.readouterr().err
