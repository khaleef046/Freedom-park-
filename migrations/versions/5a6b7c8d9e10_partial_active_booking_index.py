"""Make the active booking date index partial on PostgreSQL.

Revision ID: 5a6b7c8d9e10
Revises: 4d8e3f2a1b60
"""

from alembic import op
import sqlalchemy as sa


revision = "5a6b7c8d9e10"
down_revision = "4d8e3f2a1b60"
branch_labels = None
depends_on = None


def upgrade():
    active_statuses = sa.text("status = 'CONFIRMED' OR status = 'PENDING_PAYMENT'")
    op.drop_index("uq_active_booking_date", table_name="bookings")
    op.create_index(
        "uq_active_booking_date",
        "bookings",
        ["booking_date"],
        unique=True,
        sqlite_where=active_statuses,
        postgresql_where=active_statuses,
    )


def downgrade():
    active_statuses = sa.text("status = 'CONFIRMED' OR status = 'PENDING_PAYMENT'")
    op.drop_index("uq_active_booking_date", table_name="bookings")
    op.create_index(
        "uq_active_booking_date",
        "bookings",
        ["booking_date"],
        unique=True,
        sqlite_where=active_statuses,
    )