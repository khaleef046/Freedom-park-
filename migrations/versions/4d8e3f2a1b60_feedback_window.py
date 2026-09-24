"""Add feedback submission timestamps and one-feedback-per-booking rule.

Revision ID: 4d8e3f2a1b60
Revises: 3b7c2d1e9f40
"""

from alembic import op
import sqlalchemy as sa


revision = "4d8e3f2a1b60"
down_revision = "3b7c2d1e9f40"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("feedback")}
    indexes = {index["name"] for index in inspector.get_indexes("feedback")}
    with op.batch_alter_table("feedback", schema=None) as batch_op:
        if "submitted_at" not in columns:
            batch_op.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        if "uq_feedback_booking" not in indexes:
            batch_op.create_index(
                "uq_feedback_booking",
                ["booking_id"],
                unique=True,
                sqlite_where=sa.text("booking_id IS NOT NULL"),
            )


def downgrade():
    with op.batch_alter_table("feedback", schema=None) as batch_op:
        batch_op.drop_index("uq_feedback_booking")
        batch_op.drop_column("submitted_at")