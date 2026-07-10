"""add report owner snapshots

Revision ID: 20260704_report_owner_snap
Revises: 20260704_0920
Create Date: 2026-07-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '20260704_report_owner_snap'
down_revision = '20260704_0920'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('generated_by_username_snapshot', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('generated_by_display_name_snapshot', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('generated_by_auth_source_snapshot', sa.String(length=50), nullable=True))

    op.execute(
        """
        UPDATE reports AS r
        SET
            generated_by_username_snapshot = u.username,
            generated_by_display_name_snapshot = COALESCE(NULLIF(TRIM(u.display_name), ''), u.username),
            generated_by_auth_source_snapshot = u.auth_source
        FROM users AS u
        WHERE r.generated_by_id = u.id
          AND r.generated_by_id IS NOT NULL
          AND r.generated_by_username_snapshot IS NULL
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            SELECT tc.constraint_name
            INTO constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = 'reports'
              AND kcu.column_name = 'generated_by_id'
            LIMIT 1;

            IF constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE reports DROP CONSTRAINT %I', constraint_name);
            END IF;
        END $$;
        """
    )

    op.create_foreign_key(
        'fk_reports_generated_by_id_users',
        'reports',
        'users',
        ['generated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_reports_generated_by_id_users', 'reports', type_='foreignkey')
    op.create_foreign_key(
        'reports_generated_by_id_fkey',
        'reports',
        'users',
        ['generated_by_id'],
        ['id'],
    )

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_column('generated_by_auth_source_snapshot')
        batch_op.drop_column('generated_by_display_name_snapshot')
        batch_op.drop_column('generated_by_username_snapshot')
