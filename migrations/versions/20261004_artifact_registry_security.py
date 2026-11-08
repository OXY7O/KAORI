"""add Artifact Registry security evidence

Revision ID: 20261004_registry_security
Revises: 20261004_registry_inventory
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20261004_registry_security'
down_revision = '20261004_registry_inventory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('registry_artifacts', sa.Column('scan_status', sa.String(length=40), nullable=True))
    op.add_column('registry_artifacts', sa.Column('scan_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('registry_artifacts', sa.Column('vulnerability_summary', sa.JSON(), nullable=True))
    op.add_column('registry_artifacts', sa.Column('signature_status', sa.String(length=40), nullable=True))
    op.add_column('registry_artifacts', sa.Column('sbom_status', sa.String(length=40), nullable=True))

    op.create_table(
        'registry_scan_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=False),
        sa.Column('scanner', sa.String(length=255), nullable=True),
        sa.Column('scanner_version', sa.String(length=120), nullable=True),
        sa.Column('report_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='not_scanned'),
        sa.Column('severity_summary', sa.JSON(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['artifact_id'], ['registry_artifacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('registry_scan_snapshots', 'status', server_default=None)
    op.create_index('ix_registry_scan_snapshots_artifact_id', 'registry_scan_snapshots', ['artifact_id'])
    op.create_index(
        'ix_registry_scan_artifact_observed',
        'registry_scan_snapshots',
        ['artifact_id', 'observed_at'],
    )

    op.create_table(
        'registry_vulnerabilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_snapshot_id', sa.Integer(), nullable=False),
        sa.Column('vulnerability_id', sa.String(length=255), nullable=False),
        sa.Column('package', sa.String(length=512), nullable=False, server_default='unknown'),
        sa.Column('installed_version', sa.String(length=255), nullable=False, server_default='unknown'),
        sa.Column('fixed_version', sa.String(length=512), nullable=True),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='unknown'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['scan_snapshot_id'], ['registry_scan_snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'scan_snapshot_id',
            'vulnerability_id',
            'package',
            'installed_version',
            name='uq_registry_vulnerability_scan_identity',
        ),
    )
    op.alter_column('registry_vulnerabilities', 'package', server_default=None)
    op.alter_column('registry_vulnerabilities', 'installed_version', server_default=None)
    op.alter_column('registry_vulnerabilities', 'severity', server_default=None)
    op.create_index('ix_registry_vulnerabilities_scan_snapshot_id', 'registry_vulnerabilities', ['scan_snapshot_id'])
    op.create_index('ix_registry_vulnerabilities_severity', 'registry_vulnerabilities', ['severity'])


def downgrade() -> None:
    op.drop_index('ix_registry_vulnerabilities_severity', table_name='registry_vulnerabilities')
    op.drop_index('ix_registry_vulnerabilities_scan_snapshot_id', table_name='registry_vulnerabilities')
    op.drop_table('registry_vulnerabilities')
    op.drop_index('ix_registry_scan_artifact_observed', table_name='registry_scan_snapshots')
    op.drop_index('ix_registry_scan_snapshots_artifact_id', table_name='registry_scan_snapshots')
    op.drop_table('registry_scan_snapshots')
    op.drop_column('registry_artifacts', 'sbom_status')
    op.drop_column('registry_artifacts', 'signature_status')
    op.drop_column('registry_artifacts', 'vulnerability_summary')
    op.drop_column('registry_artifacts', 'scan_completed_at')
    op.drop_column('registry_artifacts', 'scan_status')
