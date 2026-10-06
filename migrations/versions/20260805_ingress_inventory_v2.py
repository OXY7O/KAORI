"""canonicalize Ingress Inventory network evidence

Revision ID: 20260805_ingress_inventory_v2
Revises: 20260805_service_inventory_v2
"""

from alembic import op
import sqlalchemy as sa

revision = '20260805_ingress_inventory_v2'
down_revision = '20260805_service_inventory_v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve historical compact fields in the canonical JSON evidence before
    # removing duplicated presentation columns.
    op.execute(
        """
        UPDATE ingress_inventory
        SET details = (
            COALESCE(details::jsonb, '{}'::jsonb)
            || jsonb_build_object(
                'addresses',
                CASE
                    WHEN COALESCE(address, '') NOT IN ('', '-')
                    THEN to_jsonb(regexp_split_to_array(address, '\\s*,\\s*'))
                    ELSE CASE
                        WHEN jsonb_typeof(COALESCE(details::jsonb, '{}'::jsonb) -> 'addresses') = 'array'
                        THEN COALESCE(details::jsonb, '{}'::jsonb) -> 'addresses'
                        ELSE '[]'::jsonb
                    END
                END,
                'hosts',
                CASE
                    WHEN COALESCE(host, '') NOT IN ('', '-')
                         AND CASE
                             WHEN jsonb_typeof(COALESCE(details::jsonb, '{}'::jsonb) -> 'hosts') = 'array'
                             THEN jsonb_array_length(COALESCE(details::jsonb, '{}'::jsonb) -> 'hosts')
                             ELSE 0
                         END = 0
                    THEN jsonb_build_array(host)
                    ELSE CASE
                        WHEN jsonb_typeof(COALESCE(details::jsonb, '{}'::jsonb) -> 'hosts') = 'array'
                        THEN COALESCE(details::jsonb, '{}'::jsonb) -> 'hosts'
                        ELSE '[]'::jsonb
                    END
                END,
                'specification_evidence_reported', true,
                'ingress_class_source',
                CASE
                    WHEN COALESCE(ingress_class, '') <> '' THEN 'Historical explicit class evidence'
                    ELSE 'Not Explicitly Set'
                END,
                'publication_evidence_reported',
                CASE
                    WHEN COALESCE(address, '') NOT IN ('', '-') THEN true
                    ELSE CASE
                        WHEN lower(COALESCE(details::jsonb ->> 'publication_evidence_reported', '')) IN ('true', 'false')
                        THEN (details::jsonb ->> 'publication_evidence_reported')::boolean
                        ELSE false
                    END
                END
            )
        )::json
        """
    )
    op.alter_column(
        'ingress_inventory',
        'ingress_class',
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.drop_column('ingress_inventory', 'host')
    op.drop_column('ingress_inventory', 'address')


def downgrade() -> None:
    op.add_column('ingress_inventory', sa.Column('address', sa.String(length=255), nullable=True))
    op.add_column('ingress_inventory', sa.Column('host', sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE ingress_inventory
        SET host = NULLIF(details::jsonb -> 'hosts' ->> 0, ''),
            address = NULLIF(array_to_string(
                ARRAY(SELECT jsonb_array_elements_text(COALESCE(details::jsonb -> 'addresses', '[]'::jsonb))),
                ', '
            ), '')
        """
    )
    op.alter_column(
        'ingress_inventory',
        'ingress_class',
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
