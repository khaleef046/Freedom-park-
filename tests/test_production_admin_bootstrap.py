import pytest

from app import create_app
from app.extensions import db
from app.models.user import Role, User


@pytest.fixture
def bootstrap_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _set_bootstrap_environment(monkeypatch, **overrides):
    values = {
        "BOOTSTRAP_ADMIN_USERNAME": "initial-admin",
        "BOOTSTRAP_ADMIN_NAME": "Initial Administrator",
        "BOOTSTRAP_ADMIN_PASSWORD": "a-private-test-password",
    }
    values.update(overrides)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def test_bootstrap_creates_first_super_admin_with_hashed_password(
    bootstrap_app, monkeypatch
):
    password = "a-private-test-password"
    _set_bootstrap_environment(monkeypatch, BOOTSTRAP_ADMIN_PASSWORD=password)

    result = bootstrap_app.test_cli_runner().invoke(
        args=["bootstrap-production-admin"]
    )

    assert result.exit_code == 0, result.output
    assert password not in result.output
    with bootstrap_app.app_context():
        users = User.query.all()
        assert len(users) == 1
        assert users[0].username == "initial-admin"
        assert users[0].role == Role.SUPER_ADMIN
        assert users[0].password_hash != password
        assert users[0].check_password(password)


def test_bootstrap_refuses_when_any_staff_user_exists(bootstrap_app, monkeypatch):
    _set_bootstrap_environment(monkeypatch)
    with bootstrap_app.app_context():
        existing = User(
            username="existing-staff",
            full_name="Existing Staff",
            role=Role.ADMIN,
        )
        existing.set_password("unchanged-existing-password")
        db.session.add(existing)
        db.session.commit()
        original_hash = existing.password_hash

    result = bootstrap_app.test_cli_runner().invoke(
        args=["bootstrap-production-admin"]
    )

    assert result.exit_code == 0
    assert "already exists" in result.output
    with bootstrap_app.app_context():
        assert User.query.count() == 1
        existing = User.query.filter_by(username="existing-staff").one()
        assert existing.password_hash == original_hash


@pytest.mark.parametrize(
    "missing_name",
    [
        "BOOTSTRAP_ADMIN_USERNAME",
        "BOOTSTRAP_ADMIN_NAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
    ],
)
def test_bootstrap_fails_safely_when_configuration_is_missing(
    bootstrap_app, monkeypatch, missing_name
):
    _set_bootstrap_environment(monkeypatch, **{missing_name: None})

    result = bootstrap_app.test_cli_runner().invoke(
        args=["bootstrap-production-admin"]
    )

    assert result.exit_code != 0
    assert missing_name in result.output
    with bootstrap_app.app_context():
        assert User.query.count() == 0