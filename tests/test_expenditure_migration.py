from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.models.expenditure import Expenditure
from app.models.user import User


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "3b7c2d1e9f40_add_expenditures.py"
)


def _load_migration():
    return run_path(str(MIGRATION_PATH))


def _upgrade(connection, migration):
    with Operations.context(MigrationContext.configure(connection)):
        migration["upgrade"]()


def test_existing_expenditures_table_is_adopted_without_data_loss():
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        User.__table__.create(connection)
        Expenditure.__table__.create(connection)
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, username, password_hash, full_name, role, is_active, created_at) "
                "VALUES (1, 'migration-test', 'hash', 'Migration Test', 'ADMIN', 1, "
                "'2026-09-29 12:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO expenditures "
                "(expense_date, category, amount, created_by, created_at) "
                "VALUES ('2026-09-29', 'Audit test', 12.50, 1, '2026-09-29 12:00:00')"
            )
        )

        _upgrade(connection, migration)

        assert connection.execute(
            text("SELECT category FROM expenditures")
        ).scalar_one() == "Audit test"
        index_names = {
            index["name"] for index in inspect(connection).get_indexes("expenditures")
        }
        assert "ix_expenditures_expense_date" in index_names
        assert "ix_expenditures_category" in index_names


def test_incompatible_existing_expenditures_table_is_rejected():
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE expenditures (id INTEGER PRIMARY KEY)"))

        with pytest.raises(RuntimeError, match="unexpected columns"):
            _upgrade(connection, migration)

        assert [column["name"] for column in inspect(connection).get_columns("expenditures")] == ["id"]
