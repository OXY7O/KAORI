from __future__ import annotations

import base64
import json
import re
from typing import Any

_SECRET_DATA_KEY_PATTERN = re.compile(r'^[-._a-zA-Z0-9]+$')
_EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_MAX_KUBERNETES_SECRET_BYTES = 1024 * 1024
_MAX_UPLOAD_BYTES = 1024 * 1024

def _required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def _validate_data_key(key: str) -> None:
    if len(key) > 253 or not _SECRET_DATA_KEY_PATTERN.fullmatch(key):
        raise ValueError(
            f'Invalid Secret data key: {key}. Use letters, numbers, dots, hyphens, or underscores.'
        )


def _validate_secret_size(string_data: dict[str, str]) -> None:
    payload_size = sum(
        len(key.encode()) + len(value.encode())
        for key, value in string_data.items()
    )
    if payload_size >= _MAX_KUBERNETES_SECRET_BYTES:
        raise ValueError('Replacement content must be smaller than the Kubernetes 1 MiB Secret limit.')


def _read_optional_upload(upload: Any, label: str) -> str | None:
    if upload is None or not getattr(upload, 'filename', ''):
        return None

    payload = upload.read(_MAX_UPLOAD_BYTES + 1)
    if len(payload) > _MAX_UPLOAD_BYTES:
        raise ValueError(f'{label} must be 1 MiB or smaller.')
    if not payload:
        raise ValueError(f'{label} is empty.')
    try:
        return payload.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError(f'{label} must use UTF-8 text encoding.') from exc


def _validate_ssh_private_key(raw_key: str) -> None:
    try:
        from cryptography.exceptions import UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError as exc:
        raise ValueError('SSH private-key validation is unavailable on this KAORI instance.') from exc

    key_bytes = raw_key.encode()
    try:
        try:
            serialization.load_pem_private_key(key_bytes, password=None)
        except ValueError:
            serialization.load_ssh_private_key(key_bytes, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError(
            'SSH private key must be a valid, unencrypted PEM or OpenSSH private key.'
        ) from exc


def _build_opaque_patch(form: Any, target: Any) -> dict[str, str]:
    existing_names = form.getlist('existing_key_name')
    existing_values = form.getlist('existing_key_value')
    if len(existing_names) != len(existing_values):
        raise ValueError('Existing Secret key fields are incomplete.')

    live_keys = {str(key) for key in (target.key_names or [])}
    patch: dict[str, str] = {}
    for name, value in zip(existing_names, existing_values, strict=True):
        normalized_name = name.strip()
        if normalized_name not in live_keys:
            raise ValueError('The submitted Secret key is not part of the currently loaded live Secret.')
        if value == '':
            continue
        patch[normalized_name] = value

    new_names = form.getlist('new_key_name')
    new_values = form.getlist('new_key_value')
    if len(new_names) != len(new_values):
        raise ValueError('New Secret key fields are incomplete.')

    for name, value in zip(new_names, new_values, strict=True):
        normalized_name = name.strip()
        if not normalized_name and value == '':
            continue
        if not normalized_name:
            raise ValueError('New Secret key name is required when a value is provided.')
        if value == '':
            raise ValueError(
                f'New Secret key {normalized_name} requires a value. Blank existing fields mean keep unchanged.'
            )
        _validate_data_key(normalized_name)
        if normalized_name in live_keys or normalized_name in patch:
            raise ValueError(f'Duplicate Secret data key: {normalized_name}.')
        patch[normalized_name] = value

    return patch


def _build_basic_auth_patch(form: Any) -> dict[str, str]:
    patch: dict[str, str] = {}
    username = form.get('basic_username') or ''
    password = form.get('basic_password') or ''
    password_confirm = form.get('basic_password_confirm') or ''

    if username != '':
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError('Username cannot contain only spaces.')
        patch['username'] = normalized_username

    if password != '':
        if password != password_confirm:
            raise ValueError('Password confirmation does not match.')
        patch['password'] = password
    elif password_confirm != '':
        raise ValueError('Enter the new password before its confirmation.')

    return patch


def _build_registry_patch(form: Any) -> dict[str, str]:
    server = form.get('registry_server') or ''
    username = form.get('registry_username') or ''
    password = form.get('registry_password') or ''
    email = form.get('registry_email') or ''

    submitted_fields = [server, username, password, email]
    if not any(value != '' for value in submitted_fields):
        return {}

    normalized_server = _required(server, 'Registry server')
    normalized_username = _required(username, 'Registry username')
    normalized_password = _required(password, 'Registry password or token')
    normalized_email = email.strip()

    if any(character.isspace() for character in normalized_server):
        raise ValueError('Registry server must not contain spaces.')
    if normalized_email and not _EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError('Registry email address is invalid.')

    auth = base64.b64encode(
        f'{normalized_username}:{normalized_password}'.encode()
    ).decode('ascii')
    auth_entry: dict[str, str] = {
        'username': normalized_username,
        'password': normalized_password,
        'auth': auth,
    }
    if normalized_email:
        auth_entry['email'] = normalized_email

    payload = {'auths': {normalized_server: auth_entry}}
    return {'.dockerconfigjson': json.dumps(payload, separators=(',', ':'))}


def _build_ssh_patch(form: Any, files: Any) -> dict[str, str]:
    uploaded = _read_optional_upload(files.get('ssh_private_key_file'), 'SSH private key file')
    pasted = form.get('ssh_private_key') or ''

    if uploaded is not None and pasted.strip():
        raise ValueError('Use either an uploaded SSH private key or pasted content, not both.')

    raw_key = uploaded if uploaded is not None else pasted
    if raw_key == '':
        return {}

    _validate_ssh_private_key(raw_key)
    return {'ssh-privatekey': raw_key}


def build_replace_patch(
    form: Any,
    files: Any,
    target: Any,
) -> dict[str, str]:
    if target.secret_type == 'Opaque':
        patch = _build_opaque_patch(form, target)
    elif target.secret_type == 'kubernetes.io/basic-auth':
        patch = _build_basic_auth_patch(form)
    elif target.secret_type == 'kubernetes.io/dockerconfigjson':
        patch = _build_registry_patch(form)
    elif target.secret_type == 'kubernetes.io/ssh-auth':
        patch = _build_ssh_patch(form, files)
    else:
        raise ValueError('This Secret type is not supported by the replacement workflow.')

    if not patch:
        raise ValueError(
            'No replacement values were provided. Leave a field blank to keep its existing server value, '
            'or enter at least one new value to continue.'
        )

    _validate_secret_size(patch)
    return patch

