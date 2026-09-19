"""Generalize Identity Providers into provider/adapter contracts.

Revision ID: 20260817_identity_provider_v1
Revises: 20260817_user_break_glass_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260817_identity_provider_v1'
down_revision = '20260817_user_break_glass_v1'
branch_labels = None
depends_on = None


def _values(raw: str | None) -> list[str]:
    if not raw:
        return []
    normalized = raw.replace(',', '\n')
    return [item.strip().lower() for item in normalized.splitlines() if item.strip()]


def upgrade() -> None:
    op.add_column('identity_providers', sa.Column('provider_key', sa.String(length=80), nullable=True))
    op.add_column('identity_providers', sa.Column('adapter_key', sa.String(length=80), nullable=True))
    op.add_column('identity_providers', sa.Column('configuration_json', sa.JSON(), nullable=True))
    op.add_column('identity_providers', sa.Column('admission_policy_json', sa.JSON(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            'SELECT id, provider_type, server_uri, base_dn, bind_dn, bind_password_env, user_filter, '
            'tls_mode, connect_timeout_seconds, username_attribute, email_attribute, display_name_attribute, '
            'stable_id_attribute, oidc_client_id, oidc_client_secret_env, allowed_domains, allowed_subjects '
            'FROM identity_providers'
        )
    ).mappings()
    mapping = {
        'ldap': ('ldap_directory', 'ldap', 'administrative_projection'),
        'google_oidc': ('google', 'google_oidc', 'verified_email_domain_allowlist'),
        'github_oauth': ('github', 'github_oauth2', 'subject_allowlist'),
    }
    for row in rows:
        legacy_provider_type = str(row['provider_type'] or '').strip()
        if legacy_provider_type not in mapping:
            raise RuntimeError(
                f'Unsupported legacy identity provider type {legacy_provider_type!r}; resolve the row before upgrading.'
            )
        provider_key, adapter_key, policy_profile = mapping[legacy_provider_type]
        if adapter_key == 'ldap':
            configuration = {
                'server_uri': row['server_uri'],
                'base_dn': row['base_dn'],
                'bind_dn': row['bind_dn'],
                'bind_password_env': row['bind_password_env'],
                'user_filter': row['user_filter'],
                'tls_mode': row['tls_mode'] or 'ldaps',
                'connect_timeout_seconds': row['connect_timeout_seconds'] or 5,
                'username_attribute': row['username_attribute'] or 'sAMAccountName',
                'email_attribute': row['email_attribute'] or 'mail',
                'display_name_attribute': row['display_name_attribute'] or 'displayName',
                'stable_id_attribute': row['stable_id_attribute'] or 'objectGUID',
            }
            policy_values: list[str] = []
        else:
            configuration = {
                'client_id': row['oidc_client_id'],
                'client_secret_env': row['oidc_client_secret_env'],
                'connect_timeout_seconds': row['connect_timeout_seconds'] or 5,
            }
            policy_values = _values(row['allowed_domains'] if provider_key == 'google' else row['allowed_subjects'])
        connection.execute(
            sa.text(
                'UPDATE identity_providers SET provider_key=:provider_key, adapter_key=:adapter_key, '
                'configuration_json=:configuration, admission_policy_json=:policy WHERE id=:provider_id'
            ).bindparams(
                sa.bindparam('configuration', type_=sa.JSON()),
                sa.bindparam('policy', type_=sa.JSON()),
            ),
            {
                'provider_key': provider_key,
                'adapter_key': adapter_key,
                'configuration': configuration,
                'policy': {'profile': policy_profile, 'values': policy_values},
                'provider_id': row['id'],
            },
        )

    op.execute(
        'UPDATE users SET auth_source = CASE auth_source '
        "WHEN 'ldap' THEN 'ldap_directory' "
        "WHEN 'google_oidc' THEN 'google' "
        "WHEN 'github_oauth' THEN 'github' ELSE auth_source END"
    )
    op.execute(
        'UPDATE users SET last_auth_source = CASE last_auth_source '
        "WHEN 'ldap' THEN 'ldap_directory' "
        "WHEN 'google_oidc' THEN 'google' "
        "WHEN 'github_oauth' THEN 'github' ELSE last_auth_source END"
    )

    op.alter_column('identity_providers', 'provider_key', nullable=False)
    op.alter_column('identity_providers', 'adapter_key', nullable=False)
    op.alter_column('identity_providers', 'configuration_json', nullable=False)
    op.alter_column('identity_providers', 'admission_policy_json', nullable=False)
    op.create_index('ix_identity_providers_provider_key', 'identity_providers', ['provider_key'])
    op.create_index('ix_identity_providers_adapter_key', 'identity_providers', ['adapter_key'])
    op.create_check_constraint('ck_identity_providers_provider_key', 'identity_providers', "provider_key <> ''")
    op.create_check_constraint('ck_identity_providers_adapter_key', 'identity_providers', "adapter_key <> ''")

    op.drop_index('ix_identity_providers_provider_type', table_name='identity_providers')
    for column in (
        'provider_type',
        'server_uri',
        'base_dn',
        'bind_dn',
        'bind_password_env',
        'user_filter',
        'group_base_dn',
        'group_filter',
        'tls_mode',
        'connect_timeout_seconds',
        'username_attribute',
        'email_attribute',
        'display_name_attribute',
        'stable_id_attribute',
        'oidc_issuer',
        'oidc_client_id',
        'oidc_client_secret_env',
        'allowed_domains',
        'allowed_subjects',
    ):
        op.drop_column('identity_providers', column)


def downgrade() -> None:
    op.add_column('identity_providers', sa.Column('provider_type', sa.String(length=30), nullable=True))
    op.add_column('identity_providers', sa.Column('server_uri', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('base_dn', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('bind_dn', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('bind_password_env', sa.String(length=150), nullable=True))
    op.add_column('identity_providers', sa.Column('user_filter', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('group_base_dn', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('group_filter', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('tls_mode', sa.String(length=20), nullable=True))
    op.add_column('identity_providers', sa.Column('connect_timeout_seconds', sa.Integer(), nullable=True))
    op.add_column('identity_providers', sa.Column('username_attribute', sa.String(length=100), nullable=True))
    op.add_column('identity_providers', sa.Column('email_attribute', sa.String(length=100), nullable=True))
    op.add_column('identity_providers', sa.Column('display_name_attribute', sa.String(length=100), nullable=True))
    op.add_column('identity_providers', sa.Column('stable_id_attribute', sa.String(length=100), nullable=True))
    op.add_column('identity_providers', sa.Column('oidc_issuer', sa.String(length=500), nullable=True))
    op.add_column('identity_providers', sa.Column('oidc_client_id', sa.String(length=255), nullable=True))
    op.add_column('identity_providers', sa.Column('oidc_client_secret_env', sa.String(length=150), nullable=True))
    op.add_column('identity_providers', sa.Column('allowed_domains', sa.Text(), nullable=True))
    op.add_column('identity_providers', sa.Column('allowed_subjects', sa.Text(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            'SELECT id, provider_key, adapter_key, configuration_json, admission_policy_json FROM identity_providers'
        )
    ).mappings()
    reverse = {'ldap_directory': 'ldap', 'google': 'google_oidc', 'github': 'github_oauth'}
    for row in rows:
        config = row['configuration_json'] or {}
        policy = row['admission_policy_json'] or {}
        provider_type = reverse.get(str(row['provider_key']), str(row['provider_key']))
        values = policy.get('values') if isinstance(policy, dict) else []
        values_text = '\n'.join(str(item) for item in values or [])
        connection.execute(
            sa.text(
                'UPDATE identity_providers SET provider_type=:provider_type, server_uri=:server_uri, base_dn=:base_dn, '
                'bind_dn=:bind_dn, bind_password_env=:bind_password_env, user_filter=:user_filter, tls_mode=:tls_mode, '
                'connect_timeout_seconds=:timeout, username_attribute=:username_attribute, email_attribute=:email_attribute, '
                'display_name_attribute=:display_name_attribute, stable_id_attribute=:stable_id_attribute, '
                'oidc_client_id=:client_id, oidc_client_secret_env=:client_secret_env, allowed_domains=:allowed_domains, '
                'allowed_subjects=:allowed_subjects WHERE id=:provider_id'
            ),
            {
                'provider_type': provider_type,
                'server_uri': config.get('server_uri'),
                'base_dn': config.get('base_dn'),
                'bind_dn': config.get('bind_dn'),
                'bind_password_env': config.get('bind_password_env'),
                'user_filter': config.get('user_filter'),
                'tls_mode': config.get('tls_mode') or 'ldaps',
                'timeout': config.get('connect_timeout_seconds') or 5,
                'username_attribute': config.get('username_attribute') or 'sAMAccountName',
                'email_attribute': config.get('email_attribute') or 'mail',
                'display_name_attribute': config.get('display_name_attribute') or 'displayName',
                'stable_id_attribute': config.get('stable_id_attribute') or 'objectGUID',
                'client_id': config.get('client_id'),
                'client_secret_env': config.get('client_secret_env'),
                'allowed_domains': values_text if row['provider_key'] == 'google' else None,
                'allowed_subjects': values_text if row['provider_key'] == 'github' else None,
                'provider_id': row['id'],
            },
        )

    op.execute(
        'UPDATE users SET auth_source = CASE auth_source '
        "WHEN 'ldap_directory' THEN 'ldap' WHEN 'google' THEN 'google_oidc' WHEN 'github' THEN 'github_oauth' ELSE auth_source END"
    )
    op.execute(
        'UPDATE users SET last_auth_source = CASE last_auth_source '
        "WHEN 'ldap_directory' THEN 'ldap' WHEN 'google' THEN 'google_oidc' WHEN 'github' THEN 'github_oauth' ELSE last_auth_source END"
    )

    op.alter_column('identity_providers', 'provider_type', nullable=False)
    op.create_index('ix_identity_providers_provider_type', 'identity_providers', ['provider_type'])
    op.drop_constraint('ck_identity_providers_adapter_key', 'identity_providers', type_='check')
    op.drop_constraint('ck_identity_providers_provider_key', 'identity_providers', type_='check')
    op.drop_index('ix_identity_providers_adapter_key', table_name='identity_providers')
    op.drop_index('ix_identity_providers_provider_key', table_name='identity_providers')
    op.drop_column('identity_providers', 'admission_policy_json')
    op.drop_column('identity_providers', 'configuration_json')
    op.drop_column('identity_providers', 'adapter_key')
    op.drop_column('identity_providers', 'provider_key')
