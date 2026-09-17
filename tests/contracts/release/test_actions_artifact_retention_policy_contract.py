from __future__ import annotations

from pathlib import Path


QUALITY_WORKFLOW = Path(".github/workflows/quality.yml")
DEVELOPER_WORKFLOW = Path(".github/workflows/developer-check.yml")


def test_diagnostic_artifacts_are_failure_only_and_short_lived() -> None:
    quality = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    developer = DEVELOPER_WORKFLOW.read_text(encoding="utf-8")

    expected_quality_blocks = {
        "Upload Static Diagnostics": "retention-days: 3",
        "Upload Security Diagnostics": "retention-days: 3",
        "Upload Runtime Diagnostics": "retention-days: 3",
        "Upload Smoke Diagnostics": "retention-days: 3",
    }

    for step_name, retention in expected_quality_blocks.items():
        marker = f"- name: {step_name}"
        assert marker in quality, f"missing {step_name}"
        block = quality.split(marker, 1)[1].split("\n      - name:", 1)[0]
        assert "if: ${{ failure() }}" in block, f"{step_name} must be failure-only"
        assert retention in block, f"{step_name} must use 3-day retention"

    marker = "- name: Upload Browser Diagnostics"
    assert marker in developer
    block = developer.split(marker, 1)[1].split("\n      - name:", 1)[0]
    assert "if: ${{ failure() }}" in block
    assert "retention-days: 3" in block


def test_authoritative_artifacts_keep_governed_retention() -> None:
    quality = QUALITY_WORKFLOW.read_text(encoding="utf-8")

    admission_marker = "- name: Upload Full Admission Evidence"
    assert admission_marker in quality
    admission_block = quality.split(admission_marker, 1)[1].split("\n      - name:", 1)[0]
    assert "retention-days: 14" in admission_block

    tests_marker = "- name: Upload Test Diagnostics"
    assert tests_marker in quality
    tests_block = quality.split(tests_marker, 1)[1].split("\n      - name:", 1)[0]
    assert "if: ${{ failure() }}" in tests_block
    assert "retention-days: 1" in tests_block
