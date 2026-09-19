"""runbook authoring validation and resolver compatibility

Revision ID: 20260723_runbook_validation
Revises: 20260723_knowledge_runbooks
"""

from alembic import op
import sqlalchemy as sa

revision = '20260723_runbook_validation'
down_revision = '20260723_knowledge_runbooks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('knowledge_runbook_revisions') as batch:
        batch.add_column(
            sa.Column('required_capabilities_json', sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.add_column(
            sa.Column('compatibility_profiles_json', sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.add_column(sa.Column('change_level', sa.String(length=20), nullable=False, server_default='patch'))
        batch.add_column(sa.Column('publication_validation_json', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            'fk_runbook_revision_reviewed_by', 'users', ['reviewed_by_user_id'], ['id'], ondelete='SET NULL'
        )
        batch.create_check_constraint('ck_runbook_revision_change_level', "change_level IN ('patch', 'minor', 'major')")


def downgrade() -> None:
    with op.batch_alter_table('knowledge_runbook_revisions') as batch:
        batch.drop_constraint('ck_runbook_revision_change_level', type_='check')
        batch.drop_constraint('fk_runbook_revision_reviewed_by', type_='foreignkey')
        batch.drop_column('reviewed_at')
        batch.drop_column('reviewed_by_user_id')
        batch.drop_column('publication_validation_json')
        batch.drop_column('change_level')
        batch.drop_column('compatibility_profiles_json')
        batch.drop_column('required_capabilities_json')
