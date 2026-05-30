def test_health_db_connected(client_db_ok):
    r = client_db_ok.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert "version" in body
    assert "environment" in body


def test_health_db_down(client_db_down):
    r = client_db_down.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"


def test_docs_available_in_dev(client_db_ok):
    r = client_db_ok.get("/docs")
    assert r.status_code == 200
