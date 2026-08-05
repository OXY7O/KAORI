from __future__ import annotations

import re
from typing import Any

from app.common.sensitive_uploads import (
    MAX_SENSITIVE_UPLOAD_BYTES,
    decode_utf8,
    read_optional_upload_text,
    read_required_upload_bytes,
)

DNS_LABEL_PATTERN = re.compile(r'^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$')
SECRET_DATA_KEY_PATTERN = re.compile(r'^[-._a-zA-Z0-9]+$')
EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
MAX_KUBERNETES_SECRET_BYTES = 1024 * 1024


def required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def validate_secret_name(name: str) -> None:
    labels = name.split('.')
    invalid_label = any(
        not label or len(label) > 63 or not DNS_LABEL_PATTERN.fullmatch(label)
        for label in labels
    )
    if len(name) > 253 or invalid_label:
        raise ValueError(
            'Secret name must be a valid lowercase DNS subdomain using letters, numbers, dots, or hyphens.'
        )


def validate_namespace_name(namespace: str) -> None:
    if len(namespace) > 63 or not DNS_LABEL_PATTERN.fullmatch(namespace):
        raise ValueError('Namespace must be a valid lowercase Kubernetes namespace name.')


def validate_data_key(key: str) -> None:
    if len(key) > 253 or not SECRET_DATA_KEY_PATTERN.fullmatch(key):
        raise ValueError(
            f'Invalid Secret data key: {key}. Use letters, numbers, dots, hyphens, or underscores.'
        )


def validate_secret_size(string_data: dict[str, str], *, label: str = 'Secret content') -> None:
    payload_size = sum(
        len(key.encode('utf-8')) + len(value.encode('utf-8'))
        for key, value in string_data.items()
    )
    if payload_size >= MAX_KUBERNETES_SECRET_BYTES:
        raise ValueError(f'{label} must be smaller than the Kubernetes 1 MiB limit.')


def read_required_upload(upload: Any, label: str) -> bytes:
    return read_required_upload_bytes(
        upload,
        label,
        max_bytes=MAX_SENSITIVE_UPLOAD_BYTES,
    )


def read_optional_upload(upload: Any, label: str) -> str | None:
    return read_optional_upload_text(
        upload,
        label,
        max_bytes=MAX_SENSITIVE_UPLOAD_BYTES,
    )


def validate_optional_email(email: str) -> None:
    if email and not EMAIL_PATTERN.fullmatch(email):
        raise ValueError('Registry email address is invalid.')


def validate_registry_server(server: str) -> None:
    if any(character.isspace() for character in server):
        raise ValueError('Registry server must not contain spaces.')


def validate_ssh_private_key(raw_key: str) -> None:
    try:
        from cryptography.exceptions import UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError as exc:
        raise ValueError('SSH private-key validation is unavailable on this KAORI instance.') from exc

    key_bytes = raw_key.encode('utf-8')
    try:
        try:
            serialization.load_pem_private_key(key_bytes, password=None)
        except ValueError:
            serialization.load_ssh_private_key(key_bytes, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError(
            'SSH private key must be a valid, unencrypted PEM or OpenSSH private key.'
        ) from exc
