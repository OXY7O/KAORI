"""Pure SSH host-key pin verification for issue #4799; never contacts a host.

The expected fingerprint and hostname MUST originate from a trusted asset/host-key
authority, not from a request or the untrusted remote host. This predicate does
not authorize credential resolution, SSH dispatch or a Kubernetes Run.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct

_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
_HOSTNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")
_KEY = re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")
_TYPE = "ssh-ed25519"


def _read_ssh_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    if len(blob) - offset < 4:
        raise ValueError("truncated SSH key")
    length = struct.unpack_from(">I", blob, offset)[0]
    offset += 4
    if length > len(blob) - offset:
        raise ValueError("invalid SSH string")
    return blob[offset : offset + length], offset + length


def verify_pinned_known_host(
    *, hostname: str, known_hosts_line: str, expected_fingerprint: str
) -> bool:
    """Require one exact hostname and a canonical ed25519 public key.

    Reject SSH markers, aliases, wildcards, host certificates, comments and
    ambiguous entries. No TOFU or ssh-keyscan trust promotion is performed.
    """
    if (
        not isinstance(hostname, str)
        or not _HOSTNAME.fullmatch(hostname)
        or not isinstance(known_hosts_line, str)
        or not isinstance(expected_fingerprint, str)
        or not _FINGERPRINT.fullmatch(expected_fingerprint)
    ):
        return False
    fields = known_hosts_line.split()
    if len(fields) != 3 or fields[0] != hostname or fields[1] != _TYPE:
        return False
    encoded = fields[2]
    if not _KEY.fullmatch(encoded):
        return False
    try:
        blob = base64.b64decode(encoded, validate=True)
        if base64.b64encode(blob).decode("ascii") != encoded:
            return False
        key_type, offset = _read_ssh_string(blob, 0)
        key_material, offset = _read_ssh_string(blob, offset)
    except (ValueError, binascii.Error, struct.error):
        return False
    if key_type != _TYPE.encode("ascii") or len(key_material) != 32 or offset != len(blob):
        return False
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    return expected_fingerprint == f"SHA256:{fingerprint}"
