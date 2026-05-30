"""
Auth endpoint tests — register, login, /me.

Uses SQLite in-memory so no real Postgres is needed to run these locally.
CI uses the Postgres service configured in .github/workflows/ci.yml.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def auth_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(auth_engine):
    Session = sessionmaker(bind=auth_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def auth_client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ── register ────────────────────────────────────────────────────────────────

def test_register_creates_user(auth_client):
    r = auth_client.post("/auth/register", json={
        "email": "alice@example.com",
        "display_name": "Alice",
        "password": "secret123",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["display_name"] == "Alice"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "hashed_password" not in body
    assert "id" in body


def test_register_duplicate_email(auth_client):
    auth_client.post("/auth/register", json={
        "email": "bob@example.com",
        "display_name": "Bob",
        "password": "pass",
    })
    r = auth_client.post("/auth/register", json={
        "email": "bob@example.com",
        "display_name": "Bob 2",
        "password": "pass",
    })
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_invalid_email(auth_client):
    r = auth_client.post("/auth/register", json={
        "email": "not-an-email",
        "display_name": "X",
        "password": "pass",
    })
    assert r.status_code == 422


# ── login ────────────────────────────────────────────────────────────────────

def test_login_returns_token(auth_client):
    auth_client.post("/auth/register", json={
        "email": "carol@example.com",
        "display_name": "Carol",
        "password": "mypassword",
    })
    r = auth_client.post("/auth/login", json={
        "email": "carol@example.com",
        "password": "mypassword",
    })
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_wrong_password(auth_client):
    auth_client.post("/auth/register", json={
        "email": "dave@example.com",
        "display_name": "Dave",
        "password": "correct",
    })
    r = auth_client.post("/auth/login", json={
        "email": "dave@example.com",
        "password": "wrong",
    })
    assert r.status_code == 401


def test_login_unknown_email(auth_client):
    r = auth_client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "any",
    })
    assert r.status_code == 401


# ── /me ──────────────────────────────────────────────────────────────────────

def test_me_returns_current_user(auth_client):
    auth_client.post("/auth/register", json={
        "email": "eve@example.com",
        "display_name": "Eve",
        "password": "evepass",
    })
    login = auth_client.post("/auth/login", json={
        "email": "eve@example.com",
        "password": "evepass",
    })
    token = login.json()["access_token"]

    r = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "eve@example.com"


def test_me_without_token(auth_client):
    r = auth_client.get("/auth/me")
    assert r.status_code == 403  # HTTPBearer returns 403 when no credentials


def test_me_with_invalid_token(auth_client):
    r = auth_client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


# ── JWT unit tests ────────────────────────────────────────────────────────────

def test_jwt_roundtrip():
    from app.auth.jwt import create_access_token, decode_token
    token = create_access_token("user-123", "test@example.com")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"


def test_jwt_tampered_token_rejected():
    from app.auth.jwt import create_access_token, decode_token
    from jose import JWTError
    token = create_access_token("user-123", "test@example.com")
    tampered = token[:-4] + "xxxx"
    with pytest.raises(JWTError):
        decode_token(tampered)
