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
             {"site": [{"alerts": [{"riskcode": "2", "instances": ["untrusted"]}]}]},
             {"site": [{"alerts": [{"riskcode": "2", "instances": [None]}]}]})
    for report in cases:
        assert zap_summary.summarize(report) is None
        assert "NOT VERIFIED" in zap_summary.render(zap_summary.summarize(report), SHA)


def test_invalid_source_sha_cannot_escape_markdown():
    summary = zap_summary.summarize({"site": [{"alerts": []}]})
    assert "NOT VERIFIED" in zap_summary.render(summary, "bad`injection")
