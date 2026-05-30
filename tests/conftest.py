import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_db_ok():
    """Client where the DB connection check returns True."""
    with patch("app.main.check_db_connection", return_value=True):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_db_down():
    """Client where the DB connection check returns False."""
    with patch("app.main.check_db_connection", return_value=False):
        with TestClient(app) as c:
            yield c
