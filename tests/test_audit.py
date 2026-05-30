"""
Audit log tests — append on mutations, query with filters.
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
        "id": "proj_audit_test",
        "name": "Audit Project",
        "client": "Audit Corp",
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
def audit_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(audit_engine):
    Session = sessionmaker(bind=audit_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def audit_client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _register_login(client, suffix=""):
    suffix = suffix or uuid.uuid4().hex[:8]
    email = f"audit_{suffix}@example.com"
    client.post("/auth/register", json={"email": email, "display_name": "Tester", "password": "pass"})
    token = client.post("/auth/login", json={"email": email, "password": "pass"}).json()["access_token"]
    return token


def hdrs(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_token(audit_client):
    return _register_login(audit_client, "owner_aud")


@pytest.fixture
def project_id(audit_client, owner_token):
    seed = {**SEED, "project": {**SEED["project"], "id": f"proj_{uuid.uuid4().hex[:8]}"}}
    r = audit_client.post("/projects", json=seed, headers=hdrs(owner_token))
    return r.json()["id"]


# ── audit is written on create ───────────────────────────────────────────────

def test_create_writes_audit_entry(audit_client, owner_token, project_id):
    r = audit_client.get(f"/projects/{project_id}/audit", headers=hdrs(owner_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    kinds = [e["action_kind"] for e in body["entries"]]
    assert "project.create" in kinds


# ── audit is written on update ───────────────────────────────────────────────

def test_update_writes_audit_entry(audit_client, owner_token, project_id):
    updated = {**SEED["project"], "id": project_id, "name": "Renamed Project"}
    audit_client.put(f"/projects/{project_id}", json={"project": updated}, headers=hdrs(owner_token))

    r = audit_client.get(f"/projects/{project_id}/audit", headers=hdrs(owner_token))
    kinds = [e["action_kind"] for e in r.json()["entries"]]
    assert "project.update" in kinds


# ── audit is written on share grant/revoke ───────────────────────────────────

def test_share_writes_audit_entry(audit_client, owner_token, project_id):
    collab_email = f"collab_{uuid.uuid4().hex[:6]}@example.com"
    audit_client.post("/auth/register", json={"email": collab_email, "display_name": "C", "password": "p"})
    audit_client.post(
        f"/projects/{project_id}/shares",
        json={"email": collab_email, "access_level": "read"},
        headers=hdrs(owner_token),
    )
    r = audit_client.get(
        f"/projects/{project_id}/audit",
        params={"category": "share"},
        headers=hdrs(owner_token),
    )
    assert r.status_code == 200
    assert any(e["action_kind"] == "share.grant" for e in r.json()["entries"])


# ── filtering ─────────────────────────────────────────────────────────────────

def test_filter_by_action_kind(audit_client, owner_token, project_id):
    r = audit_client.get(
        f"/projects/{project_id}/audit",
        params={"action_kind": "project.create"},
        headers=hdrs(owner_token),
    )
    entries = r.json()["entries"]
    assert all(e["action_kind"] == "project.create" for e in entries)


def test_pagination(audit_client, owner_token, project_id):
    r = audit_client.get(
        f"/projects/{project_id}/audit",
        params={"limit": 1, "offset": 0},
        headers=hdrs(owner_token),
    )
    body = r.json()
    assert len(body["entries"]) == 1
    assert body["limit"] == 1
    assert body["total"] >= 1


# ── access control ────────────────────────────────────────────────────────────

def test_audit_requires_auth(audit_client, project_id):
    r = audit_client.get(f"/projects/{project_id}/audit")
    assert r.status_code == 403


def test_audit_denied_for_non_member(audit_client, project_id):
    stranger_token = _register_login(audit_client, uuid.uuid4().hex[:6])
    r = audit_client.get(f"/projects/{project_id}/audit", headers=hdrs(stranger_token))
    assert r.status_code == 403
