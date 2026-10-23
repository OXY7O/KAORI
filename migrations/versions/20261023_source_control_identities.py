"""Persist Source Control native identities and effective-dated repository grants (#2740).

Revision ID: 20261023_sc_identity
Revises: 20261023_channel_retire

No GitHub instance or authorization grant is seeded. These are inert
identity tables until qualified SC-02/SC-03 collectors are implemented.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_sc_identity'
down_revision = '20261023_channel_retire'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_control_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_key', sa.String(80), nullable=False),
        sa.Column('host_key', sa.String(255), nullable=False),
        sa.Column('native_account_id', sa.String(80), nullable=False),
        sa.Column('account_type', sa.String(30), nullable=True),
        sa.Column('login', sa.String(255), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider_key', 'host_key', 'native_account_id', name='uq_sc_account_native'),
    )
    op.create_table(
        'source_control_installations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(),
                  sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('provider_key', sa.String(80), nullable=False),
        sa.Column('host_key', sa.String(255), nullable=False),
        sa.Column('native_app_id', sa.String(80), nullable=False),
        sa.Column('native_installation_id', sa.String(80), nullable=False),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('source_control_accounts.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('repository_scope', sa.String(16), nullable=False),
        sa.Column('grant_status', sa.String(30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('integration_instance_id', name='uq_sc_installation_connection'),
        sa.UniqueConstraint('provider_key', 'host_key', 'native_app_id', 'native_installation_id',
                            name='uq_sc_installation_native'),
    )
    op.create_table(
        'source_control_repositories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_key', sa.String(80), nullable=False),
        sa.Column('host_key', sa.String(255), nullable=False),
        sa.Column('native_repository_id', sa.String(80), nullable=False),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('source_control_accounts.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(600), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('provider_presence', sa.String(30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider_key', 'host_key', 'native_repository_id',
                            name='uq_sc_repository_native'),
    )
    op.create_index('ix_sc_repository_account', 'source_control_repositories',
                    ['account_id', 'last_observed_at'])
    op.create_table(
        'source_control_repository_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('installation_id', sa.Integer(),
                  sa.ForeignKey('source_control_installations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('repository_id', sa.Integer(),
                  sa.ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('access_status', sa.String(30), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('installation_id', 'repository_id', 'valid_from',
                            name='uq_sc_grant_transition'),
        sa.CheckConstraint('valid_until IS NULL OR valid_until > valid_from',
                           name='ck_sc_grant_valid_window'),
    )
    op.create_index(
        'uq_sc_grant_current', 'source_control_repository_grants',
        ['installation_id', 'repository_id'], unique=True,
        postgresql_where=sa.text('valid_until IS NULL'),
        sqlite_where=sa.text('valid_until IS NULL'),
    )
    op.create_index('ix_sc_grant_repository_history', 'source_control_repository_grants',
                    ['repository_id', 'valid_from'])
    op.create_table(
        'source_control_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('repository_id', sa.Integer(),
                  sa.ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('commit_sha', sa.String(128), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('repository_id', 'commit_sha', name='uq_sc_revision_repo_sha'),
    )
    op.create_index('ix_source_control_revisions_repository_id',
                    'source_control_revisions', ['repository_id'])
    op.create_table(
        'source_control_references',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('repository_id', sa.Integer(),
                  sa.ForeignKey('source_control_repositories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('full_ref', sa.String(512), nullable=False),
        sa.Column('current_revision_id', sa.Integer(),
                  sa.ForeignKey('source_control_revisions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('state', sa.String(30), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('repository_id', 'full_ref', name='uq_sc_ref_repo_name'),
    )
    op.create_index('ix_source_control_references_repository_id',
                    'source_control_references', ['repository_id'])
    op.create_table(
        'source_control_reference_transitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reference_id', sa.Integer(),
                  sa.ForeignKey('source_control_references.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('target_revision_id', sa.Integer(),
                  sa.ForeignKey('source_control_revisions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('transition_state', sa.String(30), nullable=False),
        sa.Column('provider_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('reference_id', 'observed_at', name='uq_sc_ref_transition_observation'),
    )
    op.create_index('ix_source_control_reference_transitions_reference_id',
                    'source_control_reference_transitions', ['reference_id'])


def downgrade() -> None:
    op.drop_index('ix_source_control_reference_transitions_reference_id',
                  table_name='source_control_reference_transitions')
    op.drop_table('source_control_reference_transitions')
    op.drop_index('ix_source_control_references_repository_id', table_name='source_control_references')
    op.drop_table('source_control_references')
    op.drop_index('ix_source_control_revisions_repository_id', table_name='source_control_revisions')
    op.drop_table('source_control_revisions')
    op.drop_index('ix_sc_grant_repository_history', table_name='source_control_repository_grants')
    op.drop_index('uq_sc_grant_current', table_name='source_control_repository_grants')
    op.drop_table('source_control_repository_grants')
    op.drop_index('ix_sc_repository_account', table_name='source_control_repositories')
    op.drop_table('source_control_repositories')
    op.drop_table('source_control_installations')
    op.drop_table('source_control_accounts')
