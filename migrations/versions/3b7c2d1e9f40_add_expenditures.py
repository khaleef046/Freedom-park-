"""Add owner expenditure records.

Revision ID: 3b7c2d1e9f40
Revises: 9c3f5a7b2d11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "3b7c2d1e9f40"
down_revision = "9c3f5a7b2d11"
branch_labels = None
depends_on = None


def _validate_existing_table(bind):
    inspector = inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("expenditures")}
    expected_columns = {
        "id": (sa.Integer, False, {}),
        "expense_date": (sa.Date, False, {}),
        "category": (sa.String, False, {"length": 50}),
        "amount": (sa.Numeric, False, {"precision": 10, "scale": 2}),
        "description": (sa.Text, True, {}),
        "created_by": (sa.Integer, False, {}),
        "created_at": (sa.DateTime, False, {}),
        "updated_at": (sa.DateTime, True, {}),
    }
    if set(columns) != set(expected_columns):
        raise RuntimeError("Existing expenditures table has unexpected columns.")

    for name, (type_class, nullable, attributes) in expected_columns.items():
        column = columns[name]
        if not isinstance(column["type"], type_class) or column["nullable"] != nullable:
            raise RuntimeError(f"Existing expenditures column {name!r} has an unexpected definition.")
        if any(getattr(column["type"], attribute) != value for attribute, value in attributes.items()):
            raise RuntimeError(f"Existing expenditures column {name!r} has an unexpected type.")

    primary_key = inspector.get_pk_constraint("expenditures").get("constrained_columns") or []
    if primary_key != ["id"]:
        raise RuntimeError("Existing expenditures table has an unexpected primary key.")

    foreign_keys = inspector.get_foreign_keys("expenditures")
    has_creator_foreign_key = any(
        foreign_key.get("constrained_columns") == ["created_by"]
        and foreign_key.get("referred_table") == "users"
        and foreign_key.get("referred_columns") == ["id"]
        for foreign_key in foreign_keys
    )
    if not has_creator_foreign_key:
        raise RuntimeError("Existing expenditures table is missing its creator foreign key.")

    return {index["name"]: index for index in inspector.get_indexes("expenditures")}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("expenditures"):
        existing_indexes = _validate_existing_table(bind)
    else:
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
        existing_indexes = {}

    expected_indexes = {
        "ix_expenditures_expense_date": "expense_date",
        "ix_expenditures_category": "category",
    }
    for index_name, column_name in expected_indexes.items():
        existing_index = existing_indexes.get(index_name)
        if existing_index:
            if existing_index.get("column_names") != [column_name] or existing_index.get("unique"):
                raise RuntimeError(f"Existing index {index_name!r} has an unexpected definition.")
        else:
            op.create_index(index_name, "expenditures", [column_name], unique=False)


def downgrade():
    # The table may have existed before Alembic adopted it; do not risk deleting its data.
    pass