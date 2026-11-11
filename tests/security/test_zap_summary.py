"""Privacy and incompatible-schema regressions for ZAP Actions summary (#4400)."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "zap_summary.py"
spec = importlib.util.spec_from_file_location("zap_summary", MODULE_PATH)
zap_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zap_summary)
SHA = "a" * 40


def test_sanitizes_multiple_sites_and_sensitive_payloads():
    secret = "https://internal.example/private?token=supersecret"
    report = {"site": [
        {"@name": secret, "alerts": [{"riskcode": "3", "name": secret, "instances": [{"uri": secret, "requestHeader": secret}, {}]}]},
        {"@name": secret, "alerts": [{"riskcode": 1, "description": secret, "instances": []}]},
    ]}
    rendered = zap_summary.render(zap_summary.summarize(report), SHA)
    assert "| 3 | 1 | 2 |" in rendered
    assert "| 1 | 1 | 0 |" in rendered
    assert "Sites scanned: 2" in rendered
    assert secret not in rendered
    assert "supersecret" not in rendered


def test_empty_alerts_require_present_site():
    assert "| 0 | 0 | 0 |" in zap_summary.render(zap_summary.summarize({"site": [{"alerts": []}]}), SHA)
    assert "NOT VERIFIED" in zap_summary.render(zap_summary.summarize({"site": []}), SHA)


def test_incompatible_evidence_fails_closed():
    cases = ({}, {"site": "bad"}, {"site": [{"alerts": None}]},
             {"site": [{"alerts": [{"riskcode": "unknown", "instances": []}]}]},
             {"site": [{"alerts": [{"riskcode": "2"}]}]},
             {"site": [{"alerts": [{"riskcode": True, "instances": []}]}]},
             {"site": [{"alerts": [{"riskcode": "4", "instances": []}]}]},
             {"site": [{"alerts": [{"riskcode": "2", "instances": ["untrusted"]}]}]},
             {"site": [{"alerts": [{"riskcode": "2", "instances": [None]}]}]})
    for report in cases:
        assert zap_summary.summarize(report) is None
        assert "NOT VERIFIED" in zap_summary.render(zap_summary.summarize(report), SHA)


def test_invalid_source_sha_cannot_escape_markdown():
    summary = zap_summary.summarize({"site": [{"alerts": []}]})
    assert "NOT VERIFIED" in zap_summary.render(summary, "bad`injection")


def test_oversized_report_is_not_parsed_or_echoed(tmp_path, monkeypatch, capsys):
    report = tmp_path / "zap.json"
    with report.open("wb") as stream:
        stream.truncate(zap_summary.MAX_REPORT_BYTES + 1)
    monkeypatch.setattr("sys.argv", ["zap_summary", str(report), "--source-sha", SHA])
    zap_summary.main()
    output = capsys.readouterr().out
    assert "NOT VERIFIED" in output
    assert "Sites scanned:" not in output


def test_ambiguous_or_nonfinite_json_is_not_verified(tmp_path, monkeypatch, capsys):
    # Duplicate riskcode can otherwise silently replace a High alert with Low.
    cases = (
        '{"site":[{"alerts":[{"riskcode":"3","riskcode":"0","instances":[]}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","instances":[],"confidence":NaN}]}]}',
        '{"site":[{"alerts":[{"riskcode":"3","instances":[],"confidence":Infinity}]}]}',
    )
    report = tmp_path / "zap.json"
    for raw in cases:
        report.write_text(raw, encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["zap_summary", str(report), "--source-sha", SHA])
        zap_summary.main()
        output = capsys.readouterr().out
        assert "NOT VERIFIED" in output
        assert "Sites scanned:" not in output
        assert "riskcode" not in output


def test_deeply_nested_json_is_not_verified(tmp_path, monkeypatch, capsys):
    # json.loads can raise RecursionError before schema validation begins.
    report = tmp_path / "zap.json"
    report.write_text('[' * 1500 + '0' + ']' * 1500, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["zap_summary", str(report), "--source-sha", SHA])
    zap_summary.main()
    output = capsys.readouterr().out
    assert "NOT VERIFIED" in output
    assert "Sites scanned:" not in output
    assert "Traceback" not in output


def test_bounded_read_rejects_valid_json_larger_than_limit(tmp_path, monkeypatch, capsys):
    # A valid but oversized report must not be accepted even when a stat
    # pre-check would be stale; the parser must bound the actual bytes read.
    report = tmp_path / "zap.json"
    report.write_text('{"site":[{"alerts":[]}],"padding":"' + "x" * 128 + '"}', encoding="utf-8")
    monkeypatch.setattr(zap_summary, "MAX_REPORT_BYTES", 64)
    monkeypatch.setattr("sys.argv", ["zap_summary", str(report), "--source-sha", SHA])
    zap_summary.main()
    output = capsys.readouterr().out
    assert "NOT VERIFIED" in output
    assert "Sites scanned:" not in output
    assert "padding" not in output


def test_excessive_alert_families_fail_closed(monkeypatch):
    monkeypatch.setattr(zap_summary, "MAX_ALERT_FAMILIES", 1)
    report = {"site": [{"alerts": [
        {"riskcode": "3", "instances": []},
        {"riskcode": "1", "instances": []},
    ]}]}
    assert zap_summary.summarize(report) is None
    assert "NOT VERIFIED" in zap_summary.render(zap_summary.summarize(report), SHA)


def test_excessive_instance_count_fails_closed(monkeypatch):
    monkeypatch.setattr(zap_summary, "MAX_INSTANCES", 1)
    report = {"site": [{"alerts": [
        {"riskcode": "2", "instances": [{}, {}]},
    ]}]}
    assert zap_summary.summarize(report) is None
    assert "NOT VERIFIED" in zap_summary.render(zap_summary.summarize(report), SHA)
