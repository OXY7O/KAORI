"""add Artifact Registry security and supply-chain evidence

Revision ID: 20261004_artifact_registry_sec
Revises: 20261003_artifact_registry_inv
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20261004_artifact_registry_sec'
down_revision = '20261003_artifact_registry_inv'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registry_security_collection_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('vulnerability_capability_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('signature_capability_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('sbom_capability_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('artifact_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scanned_artifact_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vulnerable_artifact_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('finding_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signature_observed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sbom_observed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_instance_id'], ['integration_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_instance_id',
            name='uq_registry_security_collection_state_integration_instance',
        ),
    )
    op.create_index(
        'ix_registry_security_collection_states_integration_instance_id',
        'registry_security_collection_states',
        ['integration_instance_id'],
        unique=False,
    )

    op.create_table(
        'registry_artifact_security_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=False),
        sa.Column('vulnerability_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('scan_status', sa.String(length=50), nullable=False, server_default='not_collected'),
        sa.Column('scan_severity', sa.String(length=30), nullable=True),
        sa.Column('scanner_name', sa.String(length=160), nullable=True),
        sa.Column('scanner_vendor', sa.String(length=160), nullable=True),
        sa.Column('scanner_version', sa.String(length=80), nullable=True),
        sa.Column('scan_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scan_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finding_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fixable_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unknown_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('negligible_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signature_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('signature_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trust_state', sa.String(length=30), nullable=False, server_default='not_evaluated'),
        sa.Column('sbom_state', sa.String(length=30), nullable=False, server_default='not_collected'),
        sa.Column('sbom_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('artifact_id', name='uq_registry_artifact_security_snapshot_artifact'),
    )
    op.create_index(
        'ix_registry_artifact_security_snapshots_artifact_id',
        'registry_artifact_security_snapshots',
        ['artifact_id'],
        unique=False,
    )

    op.create_table(
        'registry_vulnerability_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('security_snapshot_id', sa.Integer(), nullable=False),
        sa.Column('finding_key', sa.String(length=900), nullable=False),
        sa.Column('vulnerability_id', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='unknown'),
        sa.Column('package', sa.String(length=500), nullable=True),
        sa.Column('installed_version', sa.String(length=255), nullable=True),
        sa.Column('fixed_version', sa.String(length=255), nullable=True),
        sa.Column('fix_available', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('cvss_score', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('links', sa.JSON(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['security_snapshot_id'],
            ['registry_artifact_security_snapshots.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'security_snapshot_id',
            'finding_key',
            name='uq_registry_vulnerability_snapshot_key',
        ),
    )
    op.create_index(
        'ix_registry_vulnerability_findings_security_snapshot_id',
        'registry_vulnerability_findings',
        ['security_snapshot_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_registry_vulnerability_findings_security_snapshot_id',
        table_name='registry_vulnerability_findings',
    )
    op.drop_table('registry_vulnerability_findings')
    op.drop_index(
        'ix_registry_artifact_security_snapshots_artifact_id',
        table_name='registry_artifact_security_snapshots',
    )
    op.drop_table('registry_artifact_security_snapshots')
    op.drop_index(
        'ix_registry_security_collection_states_integration_instance_id',
        table_name='registry_security_collection_states',
    )
    op.drop_table('registry_security_collection_states')
