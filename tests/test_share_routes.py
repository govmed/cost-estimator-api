"""
Project sharing endpoint tests.

Covers: list shares, grant read/write, revoke, duplicate-share guard,
shared-user access to project read/update, read-only enforcement,
and owner-only delete.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

SEED = {
    "project": {
        "id": "proj_share_test",
        "name": "Shared Project",
        "client": "Client Co",
        "status": "draft",
        "engagementType": "FixedFee",
        "baseCurrency": "USD",
        "targetMarginPct": 25.0,
        "contingencyPct": 8.0,
        "managementReservePct": 3.0,
        "discountPct": 0.0,
        "fxRates": {"USD": 1.0},
        "phases": [],
        "activeScenarioId": "sc_base",
        "baseScenarioId": "sc_base",
    },
    "scenarios": [],
}


@pytest.fixture(scope="module")
def share_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(share_engine):
    Session = sessionmaker(bind=share_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def share_client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _register_and_login(client, suffix: str = "") -> tuple[str, str]:
    suffix = suffix or uuid.uuid4().hex[:8]
    email = f"user_{suffix}@example.com"
    client.post("/auth/register", json={"email": email, "display_name": f"User {suffix}", "password": "pass"})
    token = client.post("/auth/login", json={"email": email, "password": "pass"}).json()["access_token"]
    return email, token


def hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_token(share_client):
    _, token = _register_and_login(share_client, "owner")
    return token


@pytest.fixture
def project_id(share_client, owner_token):
    r = share_client.post("/projects", json=SEED, headers=hdrs(owner_token))
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def collab_email_token(share_client):
    email, token = _register_and_login(share_client, "collab")
    return email, token


# ── list shares ──────────────────────────────────────────────────────────────

def test_list_shares_empty(share_client, owner_token, project_id):
    r = share_client.get(f"/projects/{project_id}/shares", headers=hdrs(owner_token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_shares_requires_owner(share_client, project_id, collab_email_token):
    _, collab_token = collab_email_token
    r = share_client.get(f"/projects/{project_id}/shares", headers=hdrs(collab_token))
    assert r.status_code == 403


# ── grant access ─────────────────────────────────────────────────────────────

def test_grant_read_access(share_client, owner_token, project_id, collab_email_token):
    collab_email, _ = collab_email_token
    r = share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": collab_email, "access_level": "read"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == collab_email
    assert body["access_level"] == "read"
    assert body["project_id"] == project_id


def test_grant_write_access(share_client, owner_token, project_id):
    email, _ = _register_and_login(share_client, uuid.uuid4().hex[:6])
    r = share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": email, "access_level": "write"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 201
    assert r.json()["access_level"] == "write"


def test_grant_duplicate_rejected(share_client, owner_token, project_id, collab_email_token):
    collab_email, _ = collab_email_token
    # First share already exists from test_grant_read_access — try again
    r = share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": collab_email, "access_level": "write"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 400
    assert "Already shared" in r.json()["detail"]


def test_grant_invalid_access_level(share_client, owner_token, project_id):
    email, _ = _register_and_login(share_client, uuid.uuid4().hex[:6])
    r = share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": email, "access_level": "admin"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 422


def test_grant_unknown_user(share_client, owner_token, project_id):
    r = share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": "ghost@nowhere.com", "access_level": "read"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 404


def test_cannot_share_with_yourself(share_client, project_id, collab_email_token):
    collab_email, collab_token = collab_email_token
    # Make a second project owned by collab
    r2 = share_client.post("/projects", json=SEED, headers=hdrs(collab_token))
    pid2 = r2.json()["id"]
    r = share_client.post(
        f"/projects/{pid2}/shares",
        json={"email": collab_email, "access_level": "read"},
        headers=hdrs(collab_token),
    )
    assert r.status_code == 400


# ── shared user access ────────────────────────────────────────────────────────

def test_shared_read_user_can_get_project(share_client, project_id, collab_email_token):
    _, collab_token = collab_email_token
    r = share_client.get(f"/projects/{project_id}", headers=hdrs(collab_token))
    assert r.status_code == 200


def test_shared_read_user_sees_project_in_list(share_client, project_id, collab_email_token):
    _, collab_token = collab_email_token
    r = share_client.get("/projects", headers=hdrs(collab_token))
    ids = [p["id"] for p in r.json()]
    assert project_id in ids


def test_shared_read_user_cannot_update(share_client, project_id, collab_email_token):
    _, collab_token = collab_email_token
    r = share_client.put(
        f"/projects/{project_id}",
        json={"status": "underReview"},
        headers=hdrs(collab_token),
    )
    assert r.status_code == 403


def test_shared_write_user_can_update(share_client, owner_token, project_id):
    email, token = _register_and_login(share_client, uuid.uuid4().hex[:6])
    share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": email, "access_level": "write"},
        headers=hdrs(owner_token),
    )
    r = share_client.put(
        f"/projects/{project_id}",
        json={"status": "underReview"},
        headers=hdrs(token),
    )
    assert r.status_code == 200


def test_shared_write_user_cannot_delete(share_client, owner_token, project_id):
    email, token = _register_and_login(share_client, uuid.uuid4().hex[:6])
    share_client.post(
        f"/projects/{project_id}/shares",
        json={"email": email, "access_level": "write"},
        headers=hdrs(owner_token),
    )
    r = share_client.delete(f"/projects/{project_id}", headers=hdrs(token))
    assert r.status_code == 403


# ── revoke ───────────────────────────────────────────────────────────────────

def test_revoke_share(share_client, owner_token, project_id, collab_email_token):
    _, collab_token = collab_email_token
    # Get collab's user_id from /auth/me
    me = share_client.get("/auth/me", headers=hdrs(collab_token)).json()
    collab_user_id = me["id"]

    r = share_client.delete(
        f"/projects/{project_id}/shares/{collab_user_id}",
        headers=hdrs(owner_token),
    )
    assert r.status_code == 204

    # After revoke, collab can no longer access the project
    r2 = share_client.get(f"/projects/{project_id}", headers=hdrs(collab_token))
    assert r2.status_code == 403


def test_revoke_nonexistent_share(share_client, owner_token, project_id):
    r = share_client.delete(
        f"/projects/{project_id}/shares/no-such-user-id",
        headers=hdrs(owner_token),
    )
    assert r.status_code == 404
