"""
Project CRUD endpoint tests.

Uses SQLite in-memory with the full schema (users + projects).
Each test gets a fresh authenticated client via the `proj_client` fixture.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

SEED_PROJECT = {
    "project": {
        "id": "proj_test_001",
        "name": "Acme Modernization",
        "client": "Acme Corp",
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
    "scenarios": [
        {"id": "sc_base", "name": "Base Case", "isBase": True, "resources": [], "cloudLineItems": [], "otherCostLineItems": [], "assumptions": [], "overrides": {}}
    ],
}


@pytest.fixture(scope="module")
def proj_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(proj_engine):
    Session = sessionmaker(bind=proj_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def proj_client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_token(proj_client):
    """Register a user and return their JWT."""
    import uuid
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    proj_client.post("/auth/register", json={
        "email": email,
        "display_name": "Test User",
        "password": "testpass",
    })
    r = proj_client.post("/auth/login", json={"email": email, "password": "testpass"})
    return r.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── list ─────────────────────────────────────────────────────────────────────

def test_list_empty(proj_client, auth_token):
    r = proj_client.get("/projects", headers=headers(auth_token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_requires_auth(proj_client):
    r = proj_client.get("/projects")
    assert r.status_code == 403


# ── create ───────────────────────────────────────────────────────────────────

def test_create_project(proj_client, auth_token):
    r = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Acme Modernization"
    assert body["client"] == "Acme Corp"
    assert body["status"] == "draft"
    assert "state_json" in body
    assert body["state_json"]["scenarios"][0]["id"] == "sc_base"


def test_create_increments_list(proj_client, auth_token):
    proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token))
    r = proj_client.get("/projects", headers=headers(auth_token))
    assert len(r.json()) >= 1


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_project(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()
    r = proj_client.get(f"/projects/{created['id']}", headers=headers(auth_token))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_nonexistent(proj_client, auth_token):
    r = proj_client.get("/projects/no-such-id", headers=headers(auth_token))
    assert r.status_code == 404


def test_get_other_users_project(proj_client, auth_token):
    """A second user cannot read the first user's project."""
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()

    import uuid
    email2 = f"other_{uuid.uuid4().hex[:8]}@example.com"
    proj_client.post("/auth/register", json={"email": email2, "display_name": "Other", "password": "p"})
    token2 = proj_client.post("/auth/login", json={"email": email2, "password": "p"}).json()["access_token"]

    r = proj_client.get(f"/projects/{created['id']}", headers=headers(token2))
    assert r.status_code == 403


# ── update ────────────────────────────────────────────────────────────────────

def test_update_project_name(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()
    updated_project = {**SEED_PROJECT["project"], "name": "Acme Phase 2"}
    r = proj_client.put(
        f"/projects/{created['id']}",
        json={"project": updated_project},
        headers=headers(auth_token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Phase 2"


def test_update_status(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()
    r = proj_client.put(
        f"/projects/{created['id']}",
        json={"status": "underReview"},
        headers=headers(auth_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "underReview"


def test_update_invalid_status(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()
    r = proj_client.put(
        f"/projects/{created['id']}",
        json={"status": "banana"},
        headers=headers(auth_token),
    )
    assert r.status_code == 422


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_project(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()
    r = proj_client.delete(f"/projects/{created['id']}", headers=headers(auth_token))
    assert r.status_code == 204
    r2 = proj_client.get(f"/projects/{created['id']}", headers=headers(auth_token))
    assert r2.status_code == 404


def test_delete_other_users_project(proj_client, auth_token):
    created = proj_client.post("/projects", json=SEED_PROJECT, headers=headers(auth_token)).json()

    import uuid
    email2 = f"del_{uuid.uuid4().hex[:8]}@example.com"
    proj_client.post("/auth/register", json={"email": email2, "display_name": "Attacker", "password": "p"})
    token2 = proj_client.post("/auth/login", json={"email": email2, "password": "p"}).json()["access_token"]

    r = proj_client.delete(f"/projects/{created['id']}", headers=headers(token2))
    assert r.status_code == 403
