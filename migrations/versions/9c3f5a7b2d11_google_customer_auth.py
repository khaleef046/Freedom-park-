"""Add Google customer identities and allow phone-less customers.

Revision ID: 9c3f5a7b2d11
Revises: 17a80df2a5c1
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "9c3f5a7b2d11"
down_revision = "17a80df2a5c1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.alter_column(
            "phone",
            existing_type=sa.String(length=20),
            nullable=True,
        )

    if "customer_identities" not in inspect(bind).get_table_names():
        op.create_table(
            "customer_identities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("provider_subject", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("email_verified", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "provider",
                "provider_subject",
                name="uq_customer_identity_provider_subject",
            ),
        )
        with op.batch_alter_table("customer_identities", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_customer_identities_customer_id"),
                ["customer_id"],
                unique=False,
            )


def downgrade():
    with op.batch_alter_table("customer_identities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_customer_identities_customer_id"))
    op.drop_table("customer_identities")

    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.alter_column(
            "phone",
            existing_type=sa.String(length=20),
            nullable=False,
        )
