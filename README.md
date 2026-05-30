# cost-estimator-api

FastAPI backend for the SOW Cost Calculator. Phase 2 of the build — adds
multi-user storage, authentication, approval workflow, and server-side calc
validation on top of the [Phase 1 SPA](https://github.com/govmed/project-cost-estimator).

[![CI](https://github.com/govmed/cost-estimator-api/actions/workflows/ci.yml/badge.svg)](https://github.com/govmed/cost-estimator-api/actions/workflows/ci.yml)

---

## Quick start (Docker)

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD and SECRET_KEY
docker compose up --build
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Quick start (local Python)

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Needs a running Postgres — use Docker for just the DB:
docker compose up db -d

cp .env.example .env           # set DATABASE_URL to point at localhost:5432
alembic upgrade head
uvicorn app.main:app --reload
```

## Testing

```bash
pytest                         # all tests
pytest -v tests/test_health.py # single file
pytest --cov=app               # with coverage
```

Or inside Docker:

```bash
docker compose exec api pytest
```

## Stack

| Concern | Choice |
|---|---|
| Framework | FastAPI 0.115 |
| Server | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Validation | Pydantic v2 |
| Auth (B1) | Standalone JWT (python-jose + passlib) |
| Auth (B3) | Entra ID OIDC |
| Testing | pytest + httpx TestClient |

## Milestone plan

| Milestone | Capability |
|---|---|
| **B1.a** | Hello FastAPI — Docker Compose + /health + pytest ✅ |
| B1.b | Database + users table + Alembic migrations |
| B1.c | Auth — register, login, JWT, /me |
| B1.d | Project CRUD — save/load projects server-side |
| B1.e | Project sharing — read/write access grants |
| B1.f | Audit log — server-side append + query |
| B1.g | Approval workflow — status state machine |
| B2 | SPA integration — swap LocalStorageProvider for API calls |
| B3 | Entra ID SSO — OIDC via MSAL |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://sow_calc:devpassword@localhost:5432/sow_calc` | SQLAlchemy connection string |
| `SECRET_KEY` | `dev-secret-change-in-production` | JWT signing secret |
| `AUTH_MODE` | `standalone` | `standalone` or `oidc` |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `POSTGRES_PASSWORD` | `devpassword` | Used by docker-compose only |

## Related repos

| Repo | Purpose |
|---|---|
| [project-cost-estimator](https://github.com/govmed/project-cost-estimator) | React SPA (Phase 1) |
| [cost-estimator-postgresql](https://github.com/govmed/cost-estimator-postgresql) | Postgres init scripts + schema docs |
| [cost-estimator-api](https://github.com/govmed/cost-estimator-api) | This repo |
