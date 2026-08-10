from __future__ import annotations

import base64
import json
from typing import Any

from app.kubernetes_operations.secrets.validation import (
    read_optional_upload,
    required,
    validate_data_key,
    validate_optional_email,
    validate_registry_server,
    validate_secret_size,
    validate_ssh_private_key,
)


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
        validate_data_key(normalized_name)
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

    normalized_server = required(server, 'Registry server')
    normalized_username = required(username, 'Registry username')
    normalized_password = required(password, 'Registry password or token')
    normalized_email = email.strip()

    validate_registry_server(normalized_server)
    validate_optional_email(normalized_email)

    auth = base64.b64encode(f'{normalized_username}:{normalized_password}'.encode()).decode('ascii')
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
    uploaded = read_optional_upload(files.get('ssh_private_key_file'), 'SSH private key file')
    pasted = form.get('ssh_private_key') or ''

    if uploaded is not None and pasted.strip():
        raise ValueError('Use either an uploaded SSH private key or pasted content, not both.')

    raw_key = uploaded if uploaded is not None else pasted
    if raw_key == '':
        return {}

    validate_ssh_private_key(raw_key)
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

    validate_secret_size(patch, label='Replacement content')
    return patch
