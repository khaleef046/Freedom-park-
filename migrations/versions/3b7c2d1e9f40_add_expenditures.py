"""Add owner expenditure records.

Revision ID: 3b7c2d1e9f40
Revises: 9c3f5a7b2d11
"""

from alembic import op
import sqlalchemy as sa


revision = "3b7c2d1e9f40"
down_revision = "9c3f5a7b2d11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expenditures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("expenditures", schema=None) as batch_op:
        batch_op.create_index("ix_expenditures_expense_date", ["expense_date"], unique=False)
        batch_op.create_index("ix_expenditures_category", ["category"], unique=False)


def downgrade():
    op.drop_table("expenditures")