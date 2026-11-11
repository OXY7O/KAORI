"""Fail-closed canonical ZAP evidence regressions for #4400."""

import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "ci_zap_safe_summary.py"
SPEC = importlib.util.spec_from_file_location("ci_zap_safe_summary", SOURCE)
zap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zap)
SHA = "a" * 40


@pytest.mark.parametrize(
    "raw",
    [
        '{"site":[{"alerts":[{"riskcode":"3","riskcode":"0"}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","confidence":NaN}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","confidence":Infinity}]}]}',
        "[" * 1500 + "0" + "]" * 1500,
    ],
)
def test_ambiguous_nonfinite_or_deep_json_is_not_published(tmp_path, capsys, raw):
    report = tmp_path / "zap.json"
    output = tmp_path / "summary.md"
    report.write_text(raw, encoding="utf-8")
    result = zap.main(["--input", str(report), "--output", str(output), "--source-sha", SHA])
    assert result == 2
    assert not output.exists()
    assert "NOT VERIFIED" in capsys.readouterr().err


def test_bounded_read_rejects_oversized_valid_json(tmp_path, monkeypatch, capsys):
    report = tmp_path / "zap.json"
    output = tmp_path / "summary.md"
    report.write_text('{"site":[{"alerts":[]}],"padding":"' + "x" * 100 + '"}', encoding="utf-8")
    monkeypatch.setattr(zap, "MAX_REPORT_BYTES", 64)
    assert zap.main(["--input", str(report), "--output", str(output), "--source-sha", SHA]) == 2
    assert not output.exists()
    assert "NOT VERIFIED" in capsys.readouterr().err


def test_excessive_alert_families_fail_closed(monkeypatch):
    monkeypatch.setattr(zap, "MAX_ALERT_FAMILIES", 1)
    payload = {"site": [{"alerts": [{"riskcode": "3"}, {"riskcode": "1"}]}]}
    with pytest.raises(zap.UnverifiedZapReport):
        zap.render_summary(payload, SHA)


def test_safe_multi_site_counts_never_echo_raw_urls():
    secret = "https://private.example/path?token=never-publish"
    payload = {"site": [
        {"@name": secret, "alerts": [{"riskcode": "3", "uri": secret}]},
        {"@name": secret, "alerts": [{"riskcode": 1, "message": secret}]},
    ]}
    result = zap.render_summary(payload, SHA)
    assert "| High | 1 |" in result
    assert "| Low | 1 |" in result
    assert secret not in result


def test_excessive_scanned_sites_fail_closed(monkeypatch):
    monkeypatch.setattr(zap, "MAX_SITE_ENTRIES", 1)
    payload = {"site": [{"alerts": []}, {"alerts": []}]}
    with pytest.raises(zap.UnverifiedZapReport, match="Excessive scanned sites"):
        zap.render_summary(payload, SHA)


def test_site_limit_boundary_remains_valid(monkeypatch):
    monkeypatch.setattr(zap, "MAX_SITE_ENTRIES", 2)
    payload = {"site": [{"alerts": []}, {"alerts": []}]}
    summary = zap.render_summary(payload, SHA)
    assert "Scanned site entries: **2**." in summary


def test_invalid_report_removes_stale_summary_before_failure(tmp_path, capsys):
    report = tmp_path / "zap.json"
    output = tmp_path / "summary.md"
    report.write_text('{"site": null}', encoding="utf-8")
    output.write_text("stale VERIFIED-looking evidence", encoding="utf-8")

    result = zap.main(["--input", str(report), "--output", str(output), "--source-sha", SHA])

    assert result == 2
    assert not output.exists()
    assert "NOT VERIFIED" in capsys.readouterr().err


def test_valid_report_replaces_stale_summary_without_leaking_it(tmp_path):
    report = tmp_path / "zap.json"
    output = tmp_path / "summary.md"
    report.write_text('{"site": [{"alerts": []}]}', encoding="utf-8")
    output.write_text("old private payload", encoding="utf-8")

    assert zap.main(["--input", str(report), "--output", str(output), "--source-sha", SHA]) == 0
    summary = output.read_text(encoding="utf-8")
    assert "Committed source SHA" in summary
    assert "old private payload" not in summary
