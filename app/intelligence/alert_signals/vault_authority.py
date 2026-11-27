"""Fixed, deployment-owned signed Vault alert authority receipts (#5252/#5253).

Reuse the existing canonical Ed25519 evidence primitives. No signing key,
caller-selected filesystem path, public endpoint, or provider write.
"""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    canonical_statement,
    verify_statement,
)

_AUTHORITY_DIR = Path('/run/kaori/vault-alert-authority')
_NAME = re.compile(r'(recovery-[1-9][0-9]{0,17}|delivery-[1-9][0-9]{0,17}(?:-[1-9][0-9]{0,17}){2})\.(pub|json)')
_HEX_KEY = re.compile(r'[a-f0-9]{64}')
_HEX_SIGNATURE = re.compile(r'[a-f0-9]{128}')
_MAX_BYTES = 65536


def _safe_file(info: os.stat_result, *, directory: bool = False) -> bool:
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    return expected_type(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022


def _read_authority_file(name: str) -> bytes | None:
    if _NAME.fullmatch(name) is None:
        return None
    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(_AUTHORITY_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if not _safe_file(os.fstat(directory_fd), directory=True):
            return None
        if not os.fstatvfs(directory_fd).f_flag & os.ST_RDONLY:
            return None
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        info = os.fstat(file_fd)
        if not _safe_file(info) or not 0 < info.st_size <= _MAX_BYTES:
            return None
        with os.fdopen(file_fd, 'rb') as stream:
            file_fd = None
            data = stream.read(_MAX_BYTES + 1)
        return data if 0 < len(data) <= _MAX_BYTES else None
    except (OSError, AttributeError, ValueError):
        return None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def receipt_time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timedelta(0) and parsed.isoformat() == value else None


def read_signed_authority(
    name: str, *, schema: str, now: datetime
) -> tuple[dict[str, Any], str] | None:
    """Read a separately pinned exact authority, rechecking expiry on every use."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        return None
    pin = _read_authority_file(name + '.pub')
    raw = _read_authority_file(name + '.json')
    if pin is None or raw is None:
        return None
    try:
        key_text = pin.decode('ascii').strip()
        envelope = json.loads(raw)
        if not _HEX_KEY.fullmatch(key_text) or not isinstance(envelope, dict):
            return None
        if set(envelope) != {'payload', 'signature'} or canonical_statement(envelope) != raw.strip():
            return None
        payload, signature = envelope['payload'], envelope['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str) or not _HEX_SIGNATURE.fullmatch(signature):
            return None
        if payload.get('schema') != schema or payload.get('state') != 'active':
            return None
        issued, expires = receipt_time(payload.get('issued_at')), receipt_time(payload.get('expires_at'))
        if issued is None or expires is None or not timedelta(0) < expires - issued <= timedelta(hours=24):
            return None
        if not verify_statement(
            canonical_statement(payload),
            issued_at=issued,
            expires_at=expires,
            signature=bytes.fromhex(signature),
            verification_key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_text)),
            now=now,
        ):
            return None
        return payload, sha256(raw.strip()).hexdigest()
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return None
