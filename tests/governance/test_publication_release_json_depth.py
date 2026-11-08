"""Regression: excessive JSON nesting must not crash publication inventory (#4212)."""

import json
import subprocess

from scripts.publication_release_assets_inventory import inventory


def test_deeply_nested_release_metadata_fails_closed_without_disclosure():
    # A deeply nested, otherwise valid JSON document exceeds the parser's
    # recursion budget. The inventory must return sanitized INCOMPLETE.
    sensitive_marker = 'DO_NOT_ECHO_RELEASE_METADATA'
    payload = '[' * 1500 + json.dumps(sensitive_marker) + ']' * 1500

    def runner(command, **kwargs):
        assert command[:2] == ['gh', 'api']
        return subprocess.CompletedProcess(command, 0, payload)

    result = inventory('OXY7O/KAORI', runner=runner)
    assert result['assessment'] == 'INCOMPLETE'
    assert result['release_metadata_access'] == 'FAILED_OR_INCOMPLETE'
    assert result['release_count'] is None
    assert sensitive_marker not in json.dumps(result)
