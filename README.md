# vehix

Vehicle management backend: users, vehicles and rentals behind a JWT-secured REST API.

- Python 3.12+, FastAPI, Pydantic v2
- PostgreSQL 16 (local, via Podman), SQLAlchemy 2.x, Alembic
- Auth: JWT access tokens (PyJWT) and argon2 password hashing

Requirements live in [`docs/PROJECT.md`](docs/PROJECT.md). Contributor and agent rules are in
[`AGENTS.md`](AGENTS.md). Progress per acceptance criterion is in [`PROGRESS.md`](PROGRESS.md).

## Setup

Prerequisites: Podman and Python 3.12+. On macOS or Windows, run
`podman machine init && podman machine start` once.

### 1. Configure secrets

Every password and secret lives in `.env` only. It is git-ignored and never committed.

```bash
cp .env.example .env
$EDITOR .env             # replace every CHANGE_ME with your own value
git check-ignore .env    # must print ".env"
python -m app.cli check-env   # lists missing or placeholder variable NAMES, never values
```

| Variable | Notes |
|----------|-------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, `TEST_DB_NAME` | Database location and names |
| `DB_PASSWORD` | Database password (also used to start the container) |
| `JWT_SECRET` | Signing key for access tokens |
| `JWT_EXPIRE_MINUTES` | Access token lifetime |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | First admin, used by `create-admin`. The password must be 12-128 characters |
| `CORS_ORIGINS` | Optional. Comma-separated allowed origins. CORS is off when unset |
| `DOCS_ENABLED` | Optional, default `true`. `false` hides `/docs`, `/redoc` and `/openapi.json` |

### 2. Start PostgreSQL

The password is read from `.env` and passed by reference, never typed as a literal.

```bash
set -a; . ./.env; set +a
podman build -t vehicles-db -f db/Dockerfile db/
podman volume create vehicles-pgdata
POSTGRES_PASSWORD="$DB_PASSWORD" podman run -d --name vehicles-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD \
  -v vehicles-pgdata:/var/lib/postgresql/data \
  vehicles-db
```

The init script creates the `vehicles` and `vehicles_test` databases, both with `btree_gist`.
It runs only on the first start of an empty volume. To reset:
`podman rm -f vehicles-db && podman volume rm vehicles-pgdata`.

### 3. Install, migrate, run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli create-admin      # idempotent; uses ADMIN_EMAIL / ADMIN_PASSWORD
uvicorn app.main:app --reload
```

The API is served under `/api/v1`. With docs enabled, open `http://localhost:8000/docs`.
Log in with `POST /api/v1/auth/login` and send the token as `Authorization: Bearer <token>`.

## Endpoints

| Area | Endpoints |
|------|-----------|
| Health | `GET /health` (no auth) |
| Auth | `POST /auth/login` (no auth) |
| Users | `GET/PATCH /users/me`; admin: `GET/POST /users`, `GET/PATCH/DELETE /users/{id}` |
| Vehicles | `GET /vehicles`, `GET /vehicles/{id}`; admin: `POST /vehicles`, `PATCH/DELETE /vehicles/{id}` |
| Rentals | `GET/POST /rentals`, `GET/PATCH /rentals/{id}`, `POST /rentals/{id}/cancel`; admin: `DELETE /rentals/{id}`, `POST /rentals/{id}/activate`, `POST /rentals/{id}/complete` |

`activate` (`reserved -> active`) and `complete` (`active -> completed`) are admin-only additions
that the rental state machine needs. See the assumptions log in `docs/PROJECT.md`, section 10.

Every response carries an `X-Request-ID` header, and access logs include it.
Errors use one envelope: `{"error": {"code": ..., "message": ..., "details": ...}}`.

## Quality gate

Run this before every commit. It needs the database from step 2.

```bash
ruff check . && ruff format --check . && mypy app && pytest -q
```

The tests use the separate `vehicles_test` database. They reset its schema and apply the
migrations at the start of each session, and they generate throwaway passwords at runtime.
