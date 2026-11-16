"""Negative SSH host-key pin contracts: no network or credential access."""

import base64
import hashlib
import struct

import pytest

from app.integrations.orchestration.configuration_automation.providers.ansible.host_key_pin import (
    verify_pinned_known_host,
)


def _ssh_string(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def _trusted():
    blob = _ssh_string(b"ssh-ed25519") + _ssh_string(bytes(range(32)))
    encoded = base64.b64encode(blob).decode()
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return {"hostname": "worker-01.example.internal",
            "known_hosts_line": f"worker-01.example.internal ssh-ed25519 {encoded}",
            "expected_fingerprint": f"SHA256:{fingerprint}"}


def test_exact_trusted_key_is_review_qualified():
    assert verify_pinned_known_host(**_trusted()) is True


@pytest.mark.parametrize("change", [
    {"hostname": "worker-02.example.internal"},
    {"hostname": "worker-01.example.internal,other"},
    {"hostname": "*.example.internal"},
    {"expected_fingerprint": "SHA256:" + "A" * 43},
    {"expected_fingerprint": "SHA256:" + "A" * 43 + "="},
    {"expected_fingerprint": None},
    {"known_hosts_line": None},
    {"known_hosts_line": ""},
])
def test_mismatch_or_invalid_authority_fails_closed(change):
    assert verify_pinned_known_host(**(_trusted() | change)) is False


def test_host_alias_marker_comment_and_key_type_fail_closed():
    trusted = _trusted()
    line = trusted["known_hosts_line"]
    for changed in (
        line.replace("worker-01.example.internal ", "worker-01.example.internal,alias "),
        "@cert-authority " + line,
        line + " optional-comment",
        line.replace("ssh-ed25519 ", "ssh-rsa "),
        line + "\n" + line,
        line.replace("worker-01.example.internal ", "|1|hash|hash "),
    ):
        assert verify_pinned_known_host(**(trusted | {"known_hosts_line": changed})) is False


def test_malformed_key_blob_and_noncanonical_base64_fail_closed():
    trusted = _trusted()
    line = trusted["known_hosts_line"]
    for encoded in (
        base64.b64encode(b"ssh-ed25519").decode(),
        base64.b64encode(_ssh_string(b"ssh-ed25519") + _ssh_string(b"x" * 31)).decode(),
        base64.b64encode(_ssh_string(b"ssh-ed25519") + _ssh_string(b"x" * 32) + b"x").decode(),
        "!!!!",
    ):
        assert verify_pinned_known_host(
            **(trusted | {"known_hosts_line": line.rsplit(" ", 1)[0] + " " + encoded})
        ) is False
