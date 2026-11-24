"""Canonical public SSH host-key encoding for independent trust qualification (#5185).

No network acquisition, known_hosts writer, verifier authority or execution
permission is established here. Only public data may cross this boundary.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass(frozen=True, slots=True, repr=False)
class CanonicalHostKey:
    algorithm: str
    public_key: str
    digest: str


def qualify_ed25519_host_key(public_key: str, *, expected_digest: str) -> CanonicalHostKey | None:
    """Match one canonical OpenSSH Ed25519 public key to an existing candidate.

    The digest is SHA-256 over the decoded SSH wire blob, in the existing
    sha256:<lowercase hex> format. A match is not independent trust evidence.
    Reject comments, extra fields, whitespace, certificates and other key
    algorithms rather than normalizing ambiguous input.
    """
    if type(public_key) is not str or len(public_key) > 128 or type(expected_digest) is not str:
        return None
    fields = public_key.split(' ')
    if len(fields) != 2 or fields[0] != 'ssh-ed25519':
        return None
    try:
        encoded = public_key.encode('ascii')
        blob = base64.b64decode(fields[1], validate=True)
        if base64.b64encode(blob).decode('ascii') != fields[1]:
            return None
        key = serialization.load_ssh_public_key(encoded)
        if not isinstance(key, Ed25519PublicKey):
            return None
        if key.public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH) != encoded:
            return None
    except (ValueError, TypeError, UnsupportedAlgorithm, binascii.Error):
        return None
    digest = 'sha256:' + hashlib.sha256(blob).hexdigest()
    if not expected_digest.isascii() or not hmac.compare_digest(digest, expected_digest):
        return None
    return CanonicalHostKey('ssh-ed25519', public_key, digest)
