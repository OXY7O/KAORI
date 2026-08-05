from __future__ import annotations

from typing import Any

MAX_SENSITIVE_UPLOAD_BYTES = 1024 * 1024


def read_required_upload_bytes(
    upload: Any,
    label: str,
    *,
    max_bytes: int = MAX_SENSITIVE_UPLOAD_BYTES,
) -> bytes:
    if upload is None or not getattr(upload, 'filename', ''):
        raise ValueError(f'{label} is required.')
    payload = upload.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f'{label} must be {max_bytes // (1024 * 1024)} MiB or smaller.')
    if not payload:
        raise ValueError(f'{label} is empty.')
    return payload


def decode_utf8(payload: bytes, label: str) -> str:
    try:
        return payload.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError(f'{label} must use UTF-8 text encoding.') from exc


def read_optional_upload_text(
    upload: Any,
    label: str,
    *,
    max_bytes: int = MAX_SENSITIVE_UPLOAD_BYTES,
) -> str | None:
    if upload is None or not getattr(upload, 'filename', ''):
        return None
    return decode_utf8(
        read_required_upload_bytes(upload, label, max_bytes=max_bytes),
        label,
    )
