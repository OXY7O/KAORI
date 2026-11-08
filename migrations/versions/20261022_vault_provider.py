"""Add encrypted HashiCorp Vault AppRole provider registration (HV-01, #2585).

Revision ID: 20261022_vault_provider
Revises: 20261013_limit_exposure
"""

from alembic import op
import sqlalchemy as sa

revision = '20261022_vault_provider'
down_revision = '20261013_limit_exposure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vault_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('auth_mount', sa.String(length=160), nullable=False, server_default='approle'),
        sa.Column('role_id', sa.String(length=255), nullable=False),
        sa.Column('secret_id', sa.Text(), nullable=False),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('detected_version', sa.String(length=64), nullable=True),
        sa.Column('compatibility_status', sa.String(length=40), nullable=True),
        sa.Column('compatibility_profile', sa.String(length=120), nullable=True),
        sa.Column('capability_profile', sa.String(length=120), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('validation_summary', sa.JSON(), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('vault_instances')
