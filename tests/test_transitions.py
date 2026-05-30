"""
Approval workflow transition tests.

Every allowed and blocked transition is exercised, plus audit log verification.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

SEED_BASE = {
    "engagementType": "FixedFee", "baseCurrency": "USD",
    "targetMarginPct": 25.0, "contingencyPct": 8.0,
    "managementReservePct": 3.0, "discountPct": 0.0,
    "fxRates": {"USD": 1.0}, "phases": [],
    "activeScenarioId": "sc_base", "baseScenarioId": "sc_base",
}


@pytest.fixture(scope="module")
def trans_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(trans_engine):
    Session = sessionmaker(bind=trans_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def tc(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _user(tc, suffix=""):
    suffix = suffix or uuid.uuid4().hex[:8]
    email = f"wf_{suffix}@example.com"
    tc.post("/auth/register", json={"email": email, "display_name": "WF", "password": "p"})
    token = tc.post("/auth/login", json={"email": email, "password": "p"}).json()["access_token"]
    return email, token


def _project(tc, token, status="draft"):
    pid = f"proj_{uuid.uuid4().hex[:8]}"
    payload = {"project": {"id": pid, "name": "WF", "client": "", "status": status, **SEED_BASE}, "scenarios": []}
    r = tc.post("/projects", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    return r.json()["id"]


def hdrs(t):
    return {"Authorization": f"Bearer {t}"}


def transition(tc, pid, to_status, token, note=None):
    body = {"to_status": to_status}
    if note:
        body["note"] = note
    return tc.post(f"/projects/{pid}/transitions", json=body, headers=hdrs(token))


# ── happy-path transitions ────────────────────────────────────────────────────

def test_draft_to_under_review(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    r = transition(tc, pid, "underReview", t)
    assert r.status_code == 200
    assert r.json()["status"] == "underReview"


def test_under_review_back_to_draft(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    transition(tc, pid, "underReview", t)
    r = transition(tc, pid, "draft", t, note="Needs more work")
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


def test_under_review_to_approved(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    transition(tc, pid, "underReview", t)
    r = transition(tc, pid, "approved", t)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_approved_to_archived(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    transition(tc, pid, "underReview", t)
    transition(tc, pid, "approved", t)
    r = transition(tc, pid, "archived", t)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_force_archive_from_draft(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    r = transition(tc, pid, "archived", t)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


# ── blocked transitions ───────────────────────────────────────────────────────

def test_approved_cannot_go_back_to_draft(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    transition(tc, pid, "underReview", t)
    transition(tc, pid, "approved", t)
    r = transition(tc, pid, "draft", t)
    assert r.status_code == 422


def test_draft_cannot_skip_to_approved(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    r = transition(tc, pid, "approved", t)
    assert r.status_code == 422


def test_write_share_can_submit_for_review(tc):
    owner_email, owner_t = _user(tc)
    _, collab_t = _user(tc)
    collab_me = tc.get("/auth/me", headers=hdrs(collab_t)).json()
    pid = _project(tc, owner_t)
    tc.post(f"/projects/{pid}/shares",
            json={"email": collab_me["email"], "access_level": "write"},
            headers=hdrs(owner_t))
    r = transition(tc, pid, "underReview", collab_t)
    assert r.status_code == 200


def test_write_share_cannot_approve(tc):
    _, owner_t = _user(tc)
    _, collab_t = _user(tc)
    collab_me = tc.get("/auth/me", headers=hdrs(collab_t)).json()
    pid = _project(tc, owner_t)
    tc.post(f"/projects/{pid}/shares",
            json={"email": collab_me["email"], "access_level": "write"},
            headers=hdrs(owner_t))
    transition(tc, pid, "underReview", owner_t)
    r = transition(tc, pid, "approved", collab_t)
    assert r.status_code == 403


def test_read_share_cannot_transition(tc):
    _, owner_t = _user(tc)
    _, reader_t = _user(tc)
    reader_me = tc.get("/auth/me", headers=hdrs(reader_t)).json()
    pid = _project(tc, owner_t)
    tc.post(f"/projects/{pid}/shares",
            json={"email": reader_me["email"], "access_level": "read"},
            headers=hdrs(owner_t))
    r = transition(tc, pid, "underReview", reader_t)
    assert r.status_code == 403


# ── audit trail ───────────────────────────────────────────────────────────────

def test_transition_writes_audit_entry(tc):
    _, t = _user(tc)
    pid = _project(tc, t)
    transition(tc, pid, "underReview", t, note="Ready for review")
    r = tc.get(f"/projects/{pid}/audit",
               params={"action_kind": "status.transition"},
               headers=hdrs(t))
    entries = r.json()["entries"]
    assert len(entries) >= 1
    data = entries[0]["action_data"]
    assert data["from"] == "draft"
    assert data["to"] == "underReview"
    assert data["note"] == "Ready for review"
