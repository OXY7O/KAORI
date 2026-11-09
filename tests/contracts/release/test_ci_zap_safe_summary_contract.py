"""Contract tests for privacy-safe ZAP Runtime & DAST evidence publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci_zap_safe_summary import UnverifiedZapReport, main, render_summary

SHA = "a" * 40
SENSITIVE = (
    "https://internal.example.invalid/login?token=secret",
    "Authorization: Bearer private-token",
    "Cookie: sessionid=private-session",
    "<script>alert('secret')</script>",
    "runtime:5000",
    "/auth/login",
)


def _alert(code: str | int, *, count: str = "2") -> dict:
    return {
        "riskcode": code,
        "count": count,
        "name": "sensitive alert name " + SENSITIVE[0],
        "alert": SENSITIVE[1],
        "desc": SENSITIVE[2],
        "instances": [
            {
                "uri": SENSITIVE[0],
                "requestHeader": SENSITIVE[1],
                "responseBody": SENSITIVE[3],
                "cookie": SENSITIVE[2],
                "attack": SENSITIVE[3],
            }
        ],
    }


def _report() -> dict:
    return {
        "@version": "2.17.0",
        "site": [
            {
                "@name": SENSITIVE[4],
                "alerts": [_alert("3"), _alert("1")],
            },
            {
                "@host": SENSITIVE[4],
                "alerts": [_alert(2), _alert("0"), _alert(2)],
            },
        ],
    }


def test_only_allowlisted_numeric_aggregates_appear_in_markdown() -> None:
    summary = render_summary(_report(), SHA)
    assert f"Committed source SHA: `{SHA}`" in summary
    assert "| High | 1 |" in summary
    assert "| Medium | 2 |" in summary
    assert "| Low | 1 |" in summary
    assert "| Informational | 1 |" in summary
    assert "| **Total** | **5** |" in summary
    assert "Scanned site entries: **2**" in summary
    assert "not** ZAP CLI FAIL/WARN/PASS counts" in summary
    assert "not**" not in summary.split("These counts")[0]
    for value in SENSITIVE:
        assert value not in summary


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"site": []},
        {"site": [{"alerts": None}]},
        {"site": [{"alerts": []}, {"bad": "missing alerts"}]},
        {"site": [{"alerts": [_alert("4")]}]},
        {"site": [{"alerts": [_alert("HIGH")]}]},
        {"site": [{"alerts": [_alert(True)]}]},
        {"site": [{"alerts": [42]}]},
    ],
)
def test_unverifiable_input_is_rejected_not_reported_as_zero(payload: object) -> None:
    with pytest.raises(UnverifiedZapReport):
        render_summary(payload, SHA)


def test_verified_empty_alert_list_does_not_claim_the_gate_passed() -> None:
    summary = render_summary({"site": [{"alerts": []}]}, SHA)
    assert "| **Total** | **0** |" in summary
    assert "Actual gate result" in summary
    assert "Code scanning" in summary


def test_source_sha_must_be_a_real_commit_digest() -> None:
    with pytest.raises(UnverifiedZapReport):
        render_summary(_report(), "untrusted [link](https://example.invalid)")


def test_cli_writes_safe_summary_but_not_original_http_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "baseline.json"
    raw.write_text(json.dumps(_report()), encoding="utf-8")
    output = tmp_path / "summary.md"
    assert main(["--input", str(raw), "--output", str(output), "--source-sha", SHA]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    sanitized = output.read_text(encoding="utf-8")
    for value in SENSITIVE:
        assert value not in sanitized
        assert value not in captured.out


def test_cli_does_not_echo_sensitive_content_when_report_is_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tmp_path / "baseline.json"
    raw.write_text('{"site": [' + SENSITIVE[0], encoding="utf-8")
    output = tmp_path / "summary.md"
    assert main(["--input", str(raw), "--output", str(output), "--source-sha", SHA]) == 2
    captured = capsys.readouterr()
    assert "NOT VERIFIED" in captured.err
    assert not output.exists()
    for value in SENSITIVE:
        assert value not in captured.out + captured.err
