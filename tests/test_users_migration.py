"""
Structural tests for the User model and migration.

These run without a real DB — they check that the ORM definition
is internally consistent and the migration file is syntactically valid.
"""

from app.models.user import User
from app.db import Base


def test_user_tablename():
    assert User.__tablename__ == "users"


def test_user_columns():
    cols = {c.name for c in User.__table__.columns}
    expected = {
        "id", "email", "hashed_password", "display_name",
        "role", "is_active", "created_at", "updated_at",
    }
    assert expected == cols


def test_user_email_unique():
    email_col = User.__table__.columns["email"]
    assert email_col.unique is True


def test_user_in_metadata():
    assert "users" in Base.metadata.tables


def test_user_repr():
    u = User(email="test@example.com", role="admin")
    assert "test@example.com" in repr(u)
    assert "admin" in repr(u)


def test_migration_revision():
    # Import the migration module to confirm it loads without error
    import importlib
    m = importlib.import_module("alembic.versions.0001_create_users")
    assert m.revision == "0001"
    assert m.down_revision is None
