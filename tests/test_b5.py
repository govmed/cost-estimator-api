"""
B5 tests — rate card management + project templates.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, get_db

SQLITE_URL = "sqlite:///:memory:"

SAMPLE_ENTRIES = [
    {"role": "Engineer", "skillLevel": "Senior", "geography": "US-Onshore",
     "billRate": {"amount": 250, "currency": "USD"},
     "internalCostRate": {"amount": 160, "currency": "USD"}},
    {"role": "Engineer", "skillLevel": "Professional", "geography": "India-Offshore",
     "billRate": {"amount": 65, "currency": "USD"},
     "internalCostRate": {"amount": 38, "currency": "USD"}},
]

SAMPLE_PROJECT_BLOB = {
    "project": {
        "id": "proj_tmpl_src",
        "name": "Source Project",
        "client": "Acme",
        "status": "draft",
        "engagementType": "FixedFee",
        "engagementContext": "Modernization",
        "baseCurrency": "USD",
        "targetMarginPct": 25.0,
        "contingencyPct": 8.0,
        "managementReservePct": 3.0,
        "discountPct": 0.0,
        "fxRates": {"USD": 1.0},
        "phases": [{"id": "ph_1", "name": "Discovery", "order": 1, "durationWeeks": 4, "offsetWeeks": 0}],
        "activeScenarioId": "sc_base",
        "baseScenarioId": "sc_base",
    },
    "scenarios": [
        {"id": "sc_base", "projectId": "proj_tmpl_src", "name": "Base",
         "isBase": True, "order": 1, "resources": [], "cloudLineItems": [],
         "otherCostLineItems": [], "assumptions": [], "overrides": {}},
    ],
}


@pytest.fixture(scope="module")
def b5_engine():
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(b5_engine):
    Session = sessionmaker(bind=b5_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def b5c(db_session):
    def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _user(b5c, role="user"):
    suffix = uuid.uuid4().hex[:8]
    email = f"b5_{suffix}@example.com"
    b5c.post("/auth/register", json={"email": email, "display_name": "B5", "password": "p", "role": role})
    token = b5c.post("/auth/login", json={"email": email, "password": "p"}).json()["access_token"]
    return email, token


def hdrs(t):
    return {"Authorization": f"Bearer {t}"}


# ═══════════════════════════════════════════════════════════════════
# Rate card tests
# ═══════════════════════════════════════════════════════════════════

def test_list_rate_cards_empty(b5c):
    _, t = _user(b5c)
    r = b5c.get("/rate-cards", headers=hdrs(t))
    assert r.status_code == 200
    assert r.json() == []


def test_create_rate_card_admin_only(b5c):
    _, t = _user(b5c)
    r = b5c.post("/rate-cards", json={
        "name": "Standard", "version": "2026-Q1",
        "effective_date": "2026-01-01", "is_illustrative": False,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(t))
    assert r.status_code == 403


def test_create_rate_card(b5c):
    _, admin_t = _user(b5c, role="admin")
    r = b5c.post("/rate-cards", json={
        "name": "Standard 2026 Q1", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": False,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(admin_t))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Standard 2026 Q1"
    assert body["entry_count"] == 2
    assert not body["is_illustrative"]
    return body["id"], admin_t


def test_get_rate_card_full(b5c):
    _, admin_t = _user(b5c, role="admin")
    card_id = b5c.post("/rate-cards", json={
        "name": "Full Card", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": False,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(admin_t)).json()["id"]

    r = b5c.get(f"/rate-cards/{card_id}", headers=hdrs(admin_t))
    assert r.status_code == 200
    body = r.json()
    assert len(body["entries"]) == 2
    assert body["entries"][0]["role"] == "Engineer"


def test_lookup_existing_entry(b5c):
    _, admin_t = _user(b5c, role="admin")
    card_id = b5c.post("/rate-cards", json={
        "name": "Lookup Card", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": False,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(admin_t)).json()["id"]

    r = b5c.get(
        f"/rate-cards/{card_id}/lookup",
        params={"role": "Engineer", "skillLevel": "Senior", "geography": "US-Onshore"},
        headers=hdrs(admin_t),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["billRate"]["amount"] == 250


def test_lookup_missing_entry(b5c):
    _, admin_t = _user(b5c, role="admin")
    card_id = b5c.post("/rate-cards", json={
        "name": "Sparse Card", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": True,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(admin_t)).json()["id"]

    r = b5c.get(
        f"/rate-cards/{card_id}/lookup",
        params={"role": "Nonexistent", "skillLevel": "Advisor", "geography": "Mars"},
        headers=hdrs(admin_t),
    )
    assert r.status_code == 200
    assert r.json()["found"] is False


def test_update_rate_card(b5c):
    _, admin_t = _user(b5c, role="admin")
    card_id = b5c.post("/rate-cards", json={
        "name": "To Update", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": True,
        "entries": SAMPLE_ENTRIES,
    }, headers=hdrs(admin_t)).json()["id"]

    r = b5c.put(f"/rate-cards/{card_id}", json={"name": "Updated Card", "is_illustrative": False},
                headers=hdrs(admin_t))
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Card"
    assert r.json()["is_illustrative"] is False


def test_delete_rate_card(b5c):
    _, admin_t = _user(b5c, role="admin")
    card_id = b5c.post("/rate-cards", json={
        "name": "To Delete", "version": "1.0",
        "effective_date": "2026-01-01", "is_illustrative": True, "entries": [],
    }, headers=hdrs(admin_t)).json()["id"]

    r = b5c.delete(f"/rate-cards/{card_id}", headers=hdrs(admin_t))
    assert r.status_code == 204
    assert b5c.get(f"/rate-cards/{card_id}", headers=hdrs(admin_t)).status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Project template tests
# ═══════════════════════════════════════════════════════════════════

def _create_source_project(b5c, token):
    blob = {
        "project": {**SAMPLE_PROJECT_BLOB["project"], "id": f"proj_{uuid.uuid4().hex[:8]}"},
        "scenarios": SAMPLE_PROJECT_BLOB["scenarios"],
    }
    blob["scenarios"][0]["projectId"] = blob["project"]["id"]
    r = b5c.post("/projects", json=blob, headers=hdrs(token))
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def test_list_templates_empty(b5c):
    _, t = _user(b5c)
    r = b5c.get("/templates", headers=hdrs(t))
    assert r.status_code == 200
    assert r.json() == []


def test_create_template_from_project(b5c):
    _, t = _user(b5c)
    project_id = _create_source_project(b5c, t)

    r = b5c.post("/templates", json={
        "source_project_id": project_id,
        "name": "Modernization Starter",
        "description": "Standard cloud modernization template",
        "is_public": True,
    }, headers=hdrs(t))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Modernization Starter"
    assert body["engagement_type"] == "FixedFee"
    return body["id"], t


def test_list_templates_after_create(b5c):
    _, t = _user(b5c)
    project_id = _create_source_project(b5c, t)
    b5c.post("/templates", json={
        "source_project_id": project_id,
        "name": "Listed Template",
        "is_public": True,
    }, headers=hdrs(t))

    r = b5c.get("/templates", headers=hdrs(t))
    assert r.status_code == 200
    names = [tmpl["name"] for tmpl in r.json()]
    assert "Listed Template" in names


def test_instantiate_template(b5c):
    _, t = _user(b5c)
    project_id = _create_source_project(b5c, t)
    tmpl_id = b5c.post("/templates", json={
        "source_project_id": project_id,
        "name": "Instantiation Template",
        "is_public": True,
    }, headers=hdrs(t)).json()["id"]

    r = b5c.post(f"/templates/{tmpl_id}/instantiate", json={
        "name": "New Project from Template",
        "client": "Beta Corp",
        "base_currency": "USD",
    }, headers=hdrs(t))
    assert r.status_code == 200
    body = r.json()
    assert "project_id" in body
    assert "New Project from Template" in body["message"]

    # Verify the project was actually created
    proj = b5c.get(f"/projects/{body['project_id']}", headers=hdrs(t))
    assert proj.status_code == 200
    assert proj.json()["name"] == "New Project from Template"
    assert proj.json()["client"] == "Beta Corp"


def test_instantiated_project_has_fresh_ids(b5c):
    _, t = _user(b5c)
    src_id = _create_source_project(b5c, t)
    tmpl_id = b5c.post("/templates", json={
        "source_project_id": src_id,
        "name": "ID Test Template",
        "is_public": True,
    }, headers=hdrs(t)).json()["id"]

    new_id = b5c.post(f"/templates/{tmpl_id}/instantiate", json={
        "name": "Fresh IDs Test", "client": "X", "base_currency": "USD",
    }, headers=hdrs(t)).json()["project_id"]

    # New project must have a different ID from the source
    assert new_id != src_id


def test_delete_template(b5c):
    _, t = _user(b5c)
    src_id = _create_source_project(b5c, t)
    tmpl_id = b5c.post("/templates", json={
        "source_project_id": src_id,
        "name": "Delete Me",
        "is_public": True,
    }, headers=hdrs(t)).json()["id"]

    r = b5c.delete(f"/templates/{tmpl_id}", headers=hdrs(t))
    assert r.status_code == 204
    assert b5c.get(f"/templates/{tmpl_id}", headers=hdrs(t)).status_code == 404


def test_template_requires_auth(b5c):
    assert b5c.get("/templates").status_code == 403
