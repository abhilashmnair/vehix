# AGENTS.md

Instructions for AI coding agents working in this repository.
Read this file first, then `PROJECT.md` (the source of truth for requirements).

## Mission

Build the Vehicle Management backend described in `PROJECT.md`, one acceptance
criterion at a time. A criterion is "met" only when its tests pass.

## Secrets and passwords policy (strict)

Every password and secret (database password, `JWT_SECRET`, seeded admin password, etc.)
comes from the `.env` file. No exceptions.

- **Source of truth:** `.env` at the repo root, loaded via `app/config.py` (pydantic-settings, `SecretStr`).
  Variable names are listed in `.env.example`, which holds **placeholders only**, never real values.
- **If `.env` is missing, or a required variable is empty or still a placeholder:**
  1. Stop the task that needs it.
  2. Tell the user to copy `.env.example` to `.env` and fill in the values themselves.
  3. Name the missing **variable names** only, never values.
  4. Resume only after the user confirms. Do not invent, generate, or write real passwords into `.env` yourself.
- **Never ask for a password or secret in chat**, and never accept one pasted into chat. If the user
  pastes one anyway, do not repeat it, do not write it to any file, and tell them to put it in `.env`.
- **Never log or print a secret.** Do not `cat`, `grep`, `echo`, or otherwise read `.env` into the
  conversation or terminal output. To check it, use `python -m app.cli check-env`, which reports
  only which variable names are missing or unset. Settings objects must never be logged or `repr`'d with secrets.
  Application logs, error messages, and test output must not contain passwords, tokens, or DSNs that embed them.
- **Never commit a secret.**
  - `.env` must be in `.gitignore`; verify with `git check-ignore .env` before the first commit.
  - Before every commit, review `git diff --cached` for secrets and make sure `.env` is not staged.
  - If a secret was committed, stop, tell the user, and do not try to rewrite history yourself.
- **No hardcoded passwords anywhere**: not in code, tests, fixtures, docs, Dockerfiles, migrations, or shell commands.
  - Tests generate throwaway passwords at runtime (e.g. `secrets.token_urlsafe(24)`) or read them from `.env`.
  - Podman commands pass the database password by environment variable reference, never as a literal value.
- The database connection is built from `.env` parts (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, ...) in
  `config.py`, so the password is stored in exactly one place.

## Stack

- Python 3.12+, FastAPI, Pydantic v2
- PostgreSQL 16 (run locally via Podman, see `db/Dockerfile`)
- SQLAlchemy 2.x (typed ORM) + Alembic migrations, `psycopg` v3 driver
- Auth: JWT access tokens (PyJWT), password hashing with argon2 (`argon2-cffi`)
- Tests: pytest, httpx `TestClient`, a real PostgreSQL test database (no SQLite)
- Tooling: `ruff` (lint + format), `mypy` (strict on `app/`), `uv` or `pip` + `requirements*.txt`

## Repository layout

```
app/
  main.py            # FastAPI app factory, router registration, exception handlers
  config.py          # Settings from env (pydantic-settings); no hardcoded secrets
  db.py              # Engine, session dependency
  models/            # SQLAlchemy models
  schemas/           # Pydantic request/response models
  routers/           # auth.py, users.py, vehicles.py, rentals.py, health.py
  services/          # Business rules (no HTTP concerns)
  security.py        # Hashing, JWT, current-user and role dependencies
  errors.py          # Domain exceptions -> HTTP mapping
alembic/             # Migrations
db/Dockerfile        # Local Postgres for Podman
tests/               # Mirrors app/ structure
AGENTS.md
PROJECT.md
```

## Workflow (mandatory)

1. Work only on a **feature branch**, never on `main`/`master`.
   - If none exists, create `feature/vehicle-management-backend` from the default branch.
   - The GitHub repo and `origin` remote are already set up by the user. Verify with
     `git remote -v`; do not create or re-initialize the repo.
2. Pick the next unmet acceptance criterion from `PROJECT.md` (they are ordered).
3. Write the tests first, watch them fail, implement, watch them pass.
4. Run the full gate before every commit:
   ```
   ruff check . && ruff format --check . && mypy app && pytest -q
   ```
5. When (and only when) the gate is green:
   - Tick the criterion's checkbox in `PROJECT.md`.
   - Commit with a Conventional Commit message that names the criterion ID,
     e.g. `feat(rentals): AC-R3 prevent overlapping rentals`.
   - `git push origin <feature-branch>` (use `-u` the first time).
6. Never push failing tests. Never `--force` push. Never rewrite pushed history.
7. If a push fails (auth, protected branch, no remote), stop and report the exact
   error. Do not try workarounds like new remotes or changing credentials.
8. Do not open or merge a PR unless the user asks.

## Coding rules

- Routers stay thin: parse input, call a service, return a schema. Business rules live in `services/`.
- All DB access goes through a per-request session dependency; commit/rollback in one place.
- Every endpoint declares `response_model`, explicit `status_code`, and documented error responses.
- Never return `password_hash` or any internal field. Use separate `*Create`, `*Update`, `*Read` schemas.
- Use `Annotated` dependencies; use `datetime` with timezone (UTC) everywhere; money as `Numeric(10, 2)`.
- Schema changes only through Alembic migrations. Never edit an applied migration; add a new one.
- No `print`; use `logging`. Never log passwords, tokens, or full request bodies.
- Secrets and passwords follow the "Secrets and passwords policy" above. `.env` is git-ignored; commit `.env.example` (placeholders only).
- Add dependencies only when needed, pin versions, and mention why in the commit message.

## Security and permissions rules

- Authentication is required on every route except `POST /auth/login` and `GET /health`.
- Authorization is enforced server-side in dependencies/services, never trusted from the client.
- A non-admin must never be able to change `role`, `is_active`, or another user's data.
- Use `404` (not `403`) when a non-admin asks for a resource they do not own, so existence does not leak.
- Compare passwords and tokens with constant-time helpers provided by the libraries; do not roll your own crypto.

## Testing rules

- Tests run against a separate database (`vehicles_test`), created by the Podman init script.
- `tests/conftest.py` loads `.env`; if required variables are missing it fails fast with a message listing
  the missing variable **names** and telling the user to populate `.env`. It never prints values.
- No literal passwords in test code; generate them per test run.
- Each test runs in an isolated transaction or truncates tables; tests must not depend on order.
- For every endpoint test at minimum: success, `401` (no/invalid token), `403` (wrong role),
  `404`, `409`/`422` where applicable.
- Keep fixtures in `tests/conftest.py`: `client`, `admin_token`, `user_token`, factories for users/vehicles/rentals.
- Do not mock the database. Mock only external things (none exist yet).

## Definition of done (per criterion)

- Tests for the criterion exist and pass; the full suite still passes.
- Lint, format, and type checks pass.
- Migration included if the schema changed, and `alembic upgrade head` works on a fresh DB.
- `PROJECT.md` checkbox ticked; commit pushed to the feature branch.

## When requirements are unclear

Pick the safest interpretation consistent with `PROJECT.md`, record the decision under
"Assumptions" in `PROJECT.md`, and continue. Ask the user only if the choice is
irreversible or changes the public API contract.

## Out of scope unless asked

Frontend, payments, file uploads, email sending, rate limiting, multi-tenancy, deployment/CI-CD.
