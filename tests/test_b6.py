"""
B6 tests — comments, webhooks, webhook delivery on status transitions.
"""

import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

SEED = {
    "project": {
        "id": "proj_b6_test",
        "name": "B6 Project",
        "client": "Corp",
        "status": "draft",
        "engagementType": "FixedFee",
        "engagementContext": "Modernization",
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
        {"id": "sc_base", "projectId": "proj_b6_test", "name": "Base",
         "isBase": True, "order": 1, "resources": [], "cloudLineItems": [],
         "otherCostLineItems": [], "assumptions": [], "overrides": {}},
    ],
}


@pytest.fixture(scope="module")
def b6_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(b6_engine):
    Session = sessionmaker(bind=b6_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def b6c(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _login(b6c, role="user"):
    suffix = uuid.uuid4().hex[:8]
    email = f"b6_{suffix}@example.com"
    b6c.post("/auth/register", json={"email": email, "display_name": "B6", "password": "p", "role": role})
    token = b6c.post("/auth/login", json={"email": email, "password": "p"}).json()["access_token"]
    return token


def hdrs(t):
    return {"Authorization": f"Bearer {t}"}


def _project(b6c, token):
    seed = {
        "project": {**SEED["project"], "id": f"proj_{uuid.uuid4().hex[:8]}"},
        "scenarios": SEED["scenarios"],
    }
    seed["scenarios"][0]["projectId"] = seed["project"]["id"]
    r = b6c.post("/projects", json=seed, headers=hdrs(token))
    assert r.status_code == 201, r.json()
    return r.json()["id"]


# ═══════════════════════════════════════════════════════════════════
# Comment tests
# ═══════════════════════════════════════════════════════════════════

def test_list_comments_empty(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    r = b6c.get(f"/projects/{pid}/comments", headers=hdrs(t))
    assert r.status_code == 200
    assert r.json() == []


def test_create_comment(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    r = b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi",
        "entity_id": "finalPrice",
        "body": "Why is this $5M? Needs justification.",
    }, headers=hdrs(t))
    assert r.status_code == 201
    body = r.json()
    assert body["body"] == "Why is this $5M? Needs justification."
    assert body["entity_type"] == "kpi"
    assert body["entity_id"] == "finalPrice"


def test_list_comments_filtered_by_entity(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "resource", "entity_id": "res_1", "body": "Resource comment",
    }, headers=hdrs(t))
    b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi", "entity_id": "totalCost", "body": "KPI comment",
    }, headers=hdrs(t))

    r = b6c.get(f"/projects/{pid}/comments?entity_type=resource", headers=hdrs(t))
    assert all(c["entity_type"] == "resource" for c in r.json())


def test_update_comment(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    c_id = b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi", "entity_id": "x", "body": "Original",
    }, headers=hdrs(t)).json()["id"]

    r = b6c.patch(f"/projects/{pid}/comments/{c_id}",
                  json={"body": "Updated"}, headers=hdrs(t))
    assert r.status_code == 200
    assert r.json()["body"] == "Updated"


def test_cannot_edit_another_users_comment(b6c):
    t1 = _login(b6c)
    t2 = _login(b6c)
    pid = _project(b6c, t1)

    # Share with t2
    me2 = b6c.get("/auth/me", headers=hdrs(t2)).json()
    b6c.post(f"/projects/{pid}/shares",
             json={"email": me2["email"], "access_level": "write"},
             headers=hdrs(t1))

    c_id = b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi", "entity_id": "x", "body": "Owner's comment",
    }, headers=hdrs(t1)).json()["id"]

    r = b6c.patch(f"/projects/{pid}/comments/{c_id}",
                  json={"body": "Hijacked"}, headers=hdrs(t2))
    assert r.status_code == 403


def test_delete_comment(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    c_id = b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi", "entity_id": "x", "body": "Temp",
    }, headers=hdrs(t)).json()["id"]

    r = b6c.delete(f"/projects/{pid}/comments/{c_id}", headers=hdrs(t))
    assert r.status_code == 204

    comments = b6c.get(f"/projects/{pid}/comments", headers=hdrs(t)).json()
    assert not any(c["id"] == c_id for c in comments)


def test_empty_comment_rejected(b6c):
    t = _login(b6c)
    pid = _project(b6c, t)
    r = b6c.post(f"/projects/{pid}/comments", json={
        "entity_type": "kpi", "entity_id": "x", "body": "   ",
    }, headers=hdrs(t))
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# Webhook tests
# ═══════════════════════════════════════════════════════════════════

def test_list_valid_events(b6c):
    t = _login(b6c)
    r = b6c.get("/webhooks/events", headers=hdrs(t))
    assert r.status_code == 200
    events = r.json()
    assert "status.transition" in events
    assert "comment.created" in events


def test_create_webhook_admin_only(b6c):
    t = _login(b6c)
    r = b6c.post("/webhooks", json={
        "name": "Test", "url": "https://example.com/hook",
        "events": ["status.transition"],
    }, headers=hdrs(t))
    assert r.status_code == 403


def test_create_webhook(b6c):
    t = _login(b6c, role="admin")
    r = b6c.post("/webhooks", json={
        "name": "Slack Notify",
        "url": "https://hooks.slack.com/services/test",
        "events": ["status.transition", "comment.created"],
        "secret": "mysecret",
    }, headers=hdrs(t))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Slack Notify"
    assert "status.transition" in body["events"]
    return body["id"], t


def test_update_webhook(b6c):
    t = _login(b6c, role="admin")
    hook_id = b6c.post("/webhooks", json={
        "name": "To Update", "url": "https://example.com/hook",
        "events": ["status.transition"],
    }, headers=hdrs(t)).json()["id"]

    r = b6c.put(f"/webhooks/{hook_id}", json={"is_active": False}, headers=hdrs(t))
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_invalid_event_rejected(b6c):
    t = _login(b6c, role="admin")
    r = b6c.post("/webhooks", json={
        "name": "Bad", "url": "https://example.com/hook",
        "events": ["not.a.real.event"],
    }, headers=hdrs(t))
    assert r.status_code == 422


def test_webhook_fired_on_transition(b6c):
    """Verify fire_event is called during a status transition."""
    t = _login(b6c)
    pid = _project(b6c, t)

    fired_events: list[dict] = []

    def fake_fire(db, background_tasks, org_id, event, data):
        fired_events.append({"event": event, "data": data})
        return 0

    with patch("app.api.transitions.fire_event", side_effect=fake_fire):
        r = b6c.post(f"/projects/{pid}/transitions",
                     json={"to_status": "underReview", "note": "ready"},
                     headers=hdrs(t))
    assert r.status_code == 200
    assert any(e["event"] == "status.transition" for e in fired_events)
    fired = next(e for e in fired_events if e["event"] == "status.transition")
    assert fired["data"]["to"] == "underReview"
    assert fired["data"]["note"] == "ready"


def test_delete_webhook(b6c):
    t = _login(b6c, role="admin")
    hook_id = b6c.post("/webhooks", json={
        "name": "Delete Me", "url": "https://example.com/hook",
        "events": ["status.transition"],
    }, headers=hdrs(t)).json()["id"]

    r = b6c.delete(f"/webhooks/{hook_id}", headers=hdrs(t))
    assert r.status_code == 204
