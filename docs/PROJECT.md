# PROJECT.md: Vehicle Management Backend

A REST API backend for managing vehicles, rentals, and users.
Stack: Python (FastAPI) + PostgreSQL. Agents must also follow `AGENTS.md`.

## 1. Goals

- CRUD for **vehicles** and **rentals**.
- **Admins** have full CRUD on **users**.
- Every **user** can view and edit their own profile.
- Correct permission checks and correct HTTP status codes on every endpoint.

## 2. Roles and permission matrix

Two roles: `admin`, `user`.

| Resource / action                 | Anonymous | User            | Admin |
|-----------------------------------|-----------|-----------------|-------|
| Login                             | yes       | yes             | yes   |
| Health check                      | yes       | yes             | yes   |
| Read own profile (`/users/me`)    | no        | yes             | yes   |
| Edit own profile (name, email, password) | no | yes             | yes   |
| Change own `role` / `is_active`   | no        | **no (403)**    | no (see 6.3) |
| List/get/create/update/delete any user | no   | no (403)        | yes   |
| List/get vehicles                 | no        | yes             | yes   |
| Create/update/delete vehicles     | no        | no (403)        | yes   |
| Create rental (for self)          | no        | yes             | yes (can set any user) |
| List/get rentals                  | no        | own only        | all   |
| Update rental (dates, notes)      | no        | own, while `reserved` | any |
| Cancel/complete rental            | no        | cancel own      | any   |
| Delete rental (hard)              | no        | no (403)        | yes   |

> Assumption: vehicles are fleet inventory managed by admins; users browse and rent.
> If the owner wants users to manage their own vehicles instead, change this table
> first, then update the criteria.

## 3. Data model

**users**: `id` (UUID PK), `email` (unique, case-insensitive via `citext` or lower index),
`full_name`, `password_hash`, `role` (`admin|user`), `is_active` (bool, default true),
`created_at`, `updated_at`.

**vehicles**: `id` (UUID PK), `license_plate` (unique, normalized uppercase), `vin` (unique, nullable),
`make`, `model`, `year`, `daily_rate` (Numeric(10,2) > 0), `status`
(`available|maintenance|retired`), `created_at`, `updated_at`, `deleted_at` (soft delete).

**rentals**: `id` (UUID PK), `user_id` FK, `vehicle_id` FK, `start_date`, `end_date`,
`status` (`reserved|active|completed|cancelled`), `total_price` (Numeric, computed server-side
from `daily_rate` at creation, so the price is frozen), `notes`, `created_at`, `updated_at`.

Constraints (enforced in the DB, not only in code):
- `CHECK (end_date >= start_date)`.
- **No overlapping non-cancelled rentals for the same vehicle**: PostgreSQL exclusion constraint
  using `btree_gist` on `(vehicle_id WITH =, daterange(start_date, end_date, '[]') WITH &&)`
  `WHERE (status IN ('reserved','active'))`.
- FKs use `ON DELETE RESTRICT`.

## 4. API contract

Base path `/api/v1`. JSON only. Auth via `Authorization: Bearer <JWT>`.

### Auth
- `POST /auth/login` (email + password) -> `200` token; `401` bad credentials or inactive user.

### Users
- `GET /users/me` -> `200`
- `PATCH /users/me` -> `200` (fields: `full_name`, `email`, `password`; password change requires `current_password`)
- `GET /users` (admin) -> `200` paginated
- `POST /users` (admin) -> `201`
- `GET /users/{id}` (admin) -> `200`
- `PATCH /users/{id}` (admin) -> `200` (may change role/is_active)
- `DELETE /users/{id}` (admin) -> `204`

### Vehicles
- `GET /vehicles` (any auth; filters: `status`, `make`, `available_from`/`available_to`) -> `200` paginated
- `GET /vehicles/{id}` -> `200`
- `POST /vehicles` (admin) -> `201` + `Location` header
- `PATCH /vehicles/{id}` (admin) -> `200`
- `DELETE /vehicles/{id}` (admin) -> `204` (soft delete)

### Rentals
- `GET /rentals` (user: own; admin: all, optional `user_id`/`vehicle_id`/`status` filters) -> `200` paginated
- `POST /rentals` -> `201` + `Location` header
- `GET /rentals/{id}` -> `200`
- `PATCH /rentals/{id}` -> `200`
- `POST /rentals/{id}/cancel` -> `200`
- `DELETE /rentals/{id}` (admin) -> `204`

### Misc
- `GET /health` -> `200` (also checks DB connectivity; `503` if DB down).

## 5. HTTP status code rules

| Code | When |
|------|------|
| 200  | Successful read/update/action |
| 201  | Resource created (with `Location`) |
| 204  | Successful delete, no body |
| 400  | Malformed request that is not a validation error (e.g. bad pagination cursor) |
| 401  | Missing, invalid, or expired token; wrong credentials; deactivated user. Include `WWW-Authenticate: Bearer` |
| 403  | Authenticated but role not allowed (e.g. user calling admin endpoint, user changing own role) |
| 404  | Resource does not exist, **or** exists but the non-admin caller does not own it |
| 409  | Uniqueness conflict (email, license plate, VIN), overlapping rental, deleting a vehicle/user with active rentals, invalid state transition, removing the last admin |
| 422  | Schema validation failure (FastAPI/Pydantic default) incl. `end_date < start_date`, non-positive rate |
| 500  | Unexpected error; never leak stack traces or SQL |
| 503  | Database unavailable (health check) |

Error body is uniform:

```json
{ "error": { "code": "rental_overlap", "message": "Vehicle is already booked for these dates." } }
```

Validation errors keep FastAPI's `detail` shape or are wrapped in the same envelope (pick one, document it, test it).

## 6. Business rules and caveats

### 6.1 Auth and passwords
- Passwords hashed with argon2; minimum length 12; never returned or logged.
- Infrastructure passwords and secrets (DB password, `JWT_SECRET`, seeded admin password) come only from `.env`; none are hardcoded anywhere, including tests (tests generate throwaway passwords at runtime).
- JWT contains `sub` (user id), `role`, `exp` (default 30 min), signed with `JWT_SECRET` from env.
- Role and `is_active` are **re-checked from the DB** on each request, so deactivating or demoting a user takes effect immediately.
- Login error message is identical for unknown email and wrong password (no user enumeration).
- Emails normalized to lowercase on write and compared case-insensitively.

### 6.2 Users
- Users cannot change their own `role` or `is_active`: `403` if they try, rather than silently ignoring.
- Self-update must not allow changing another user's data by passing an `id`.
- Deleting a user with rentals: `409` if they have `reserved`/`active` rentals. Otherwise prefer **deactivating** (`is_active=false`); hard delete is allowed only if no rental history exists (FK `RESTRICT`).
- First admin is created by an idempotent seed command (`python -m app.cli create-admin`) using env vars. There is no public signup endpoint.

### 6.3 Admin safety
- An admin cannot delete, deactivate, or demote themselves if they are the **last active admin**: `409`.

### 6.4 Vehicles
- `license_plate` normalized (trim, uppercase) before uniqueness check.
- Vehicle `status` `maintenance`/`retired` cannot be rented: `409`.
- Delete is **soft** (`deleted_at`); soft-deleted vehicles are hidden from lists and return `404`. Deleting a vehicle with `reserved`/`active` rentals: `409`.
- Year range sanity check (e.g. 1950 to current year + 1).

### 6.5 Rentals
- Dates are calendar dates; the range is inclusive; `start_date` cannot be in the past on creation (for users; admins may backdate).
- Overlap protection is enforced by the DB exclusion constraint; the service maps the violation to `409`. This avoids race conditions under concurrent requests. Add a concurrency test.
- `total_price = daily_rate * number_of_days` (inclusive), computed server-side; client-supplied price is ignored/rejected.
- State machine: `reserved -> active -> completed`, `reserved|active -> cancelled`. Anything else: `409`.
- A user cannot edit dates once the rental is `active`/`completed`/`cancelled`: `409`.
- Users cannot create rentals for another user (`403` if `user_id` differs); admins can.

### 6.6 General
- Pagination on all list endpoints: `limit` (default 20, max 100), `offset`; response includes `items` and `total`. Over-limit -> `422`.
- Stable sort order (`created_at`, then `id`).
- All timestamps stored as UTC `timestamptz`.
- `PATCH` is partial update; unknown fields are rejected (`extra="forbid"`).
- CORS: disabled by default; configurable allowed origins via env.
- OpenAPI docs enabled in dev, configurable off in prod.
- Request IDs in logs; no PII in logs.

## 7. Local development

Prerequisites: Podman, Python 3.12+. (On macOS/Windows run `podman machine init && podman machine start` once.)

```bash
# Environment: YOU fill in the values (see section 7.1). Never paste them into chat or commit them.
cp .env.example .env
$EDITOR .env             # replace every CHANGE_ME placeholder
git check-ignore .env    # must print ".env"

# Build and run Postgres (data persisted in a named volume).
# The password is read from .env and passed by reference, never typed as a literal.
set -a; . ./.env; set +a
podman build -t vehicles-db -f db/Dockerfile db/
podman volume create vehicles-pgdata
POSTGRES_PASSWORD="$DB_PASSWORD" podman run -d --name vehicles-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD \
  -v vehicles-pgdata:/var/lib/postgresql/data \
  vehicles-db

# App
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli create-admin
uvicorn app.main:app --reload

# Tests
pytest -q
```

The init script creates two databases: `vehicles` and `vehicles_test`, both with the `btree_gist` extension.
To reset: `podman rm -f vehicles-db && podman volume rm vehicles-pgdata`.

### 7.1 Environment variables (`.env`)

All passwords and secrets live only in `.env` (git-ignored). `.env.example` is committed with
placeholders only:

```
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=CHANGE_ME
DB_NAME=vehicles
TEST_DB_NAME=vehicles_test
JWT_SECRET=CHANGE_ME
JWT_EXPIRE_MINUTES=30
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=CHANGE_ME
```

Rules:
- The app builds the DB URL from these parts, so the password exists in one place only.
- Startup, the CLI, and the test suite fail fast if a variable is missing or still `CHANGE_ME`,
  reporting variable **names** only.
- If `.env` is missing, the agent stops and asks the user to create it. It never asks for values
  in chat, never reads or prints `.env`, and never commits it (see `AGENTS.md`).
- `python -m app.cli check-env` validates the file without revealing any value.

## 8. Acceptance criteria

Work in order. Tick a box only when its tests pass, then commit and push to the feature branch
(see `AGENTS.md`). Commit message references the ID.

### Foundation
- [x] **AC-F0** Secrets handling: `.env` is git-ignored, `.env.example` has placeholders only, config uses `SecretStr`, `python -m app.cli check-env` reports missing/placeholder variable names without printing values, and a missing `.env` produces a clear "populate `.env`" error (tested).
- [x] **AC-F1** Project scaffold, config from `.env`, `GET /health` returns `200`, DB connection works; pytest runs green against `vehicles_test`.
- [x] **AC-F2** Alembic set up; initial migration creates `users`, `vehicles`, `rentals` with all constraints (including `btree_gist` exclusion); migration applies on an empty DB.
- [x] **AC-F3** Uniform error envelope and exception handlers (`401/403/404/409/422/500`) with tests.

### Auth and users
- [x] **AC-A1** `POST /auth/login` succeeds with valid credentials; `401` for wrong password, unknown email, inactive user (identical message).
- [x] **AC-A2** Protected routes return `401` without/with invalid/expired token; role and `is_active` re-checked from DB.
- [x] **AC-U1** `GET/PATCH /users/me` work; password change requires `current_password`; `role`/`is_active` change attempts return `403`; response never includes password data.
- [x] **AC-U2** Admin `POST /users` (`201`), duplicate email (`409`), weak password/invalid email (`422`), non-admin (`403`).
- [x] **AC-U3** Admin `GET /users` (paginated) and `GET /users/{id}` (`200/404`); non-admin `403`.
- [x] **AC-U4** Admin `PATCH /users/{id}` incl. role/active changes; `404` unknown id; `409` email conflict.
- [x] **AC-U5** Admin `DELETE /users/{id}` (`204`); `409` for user with active rentals or for the last admin; `404` unknown id.
- [x] **AC-U6** CLI `create-admin` is idempotent and tested.

### Vehicles
- [x] **AC-V1** Admin `POST /vehicles` (`201` + `Location`); duplicate plate/VIN `409`; invalid data `422`; user `403`.
- [x] **AC-V2** `GET /vehicles` and `GET /vehicles/{id}` for any authenticated user; pagination and filters; soft-deleted hidden; `404` unknown.
- [x] **AC-V3** Admin `PATCH /vehicles/{id}` (`200`), conflicts `409`, user `403`.
- [x] **AC-V4** Admin `DELETE /vehicles/{id}` soft-deletes (`204`); `409` with active/reserved rentals; later `GET` is `404`.

### Rentals
- [x] **AC-R1** `POST /rentals` creates for self (`201` + `Location`), server-computed `total_price`; `422` for invalid dates; `409` for non-rentable vehicle; `404` for unknown/deleted vehicle; user cannot create for others (`403`); admin can.
- [x] **AC-R2** Overlapping rentals rejected with `409` (including a concurrent-request test); adjacent and cancelled-overlap bookings allowed.
- [x] **AC-R3** `GET /rentals` and `GET /rentals/{id}`: user sees only own (other's id gives `404`), admin sees all with filters; paginated.
- [x] **AC-R4** `PATCH /rentals/{id}`: owner can edit only while `reserved`; re-checks overlap and recomputes price; admin can edit any; invalid state `409`.
- [x] **AC-R5** `POST /rentals/{id}/cancel` and status transitions follow the state machine; invalid transitions `409`.
- [x] **AC-R6** Admin `DELETE /rentals/{id}` (`204`); user `403`.

### Hardening
- [x] **AC-H1** Permission matrix test: a parametrized test hits every endpoint as anonymous/user/admin and asserts the expected status from section 2.
- [x] **AC-H2** `ruff`, `mypy`, and `pytest` all green from a fresh clone following section 7; `README` section or this file is accurate.

## 9. Global done conditions

- All boxes above are ticked.
- `pytest -q` passes from a clean database.
- The feature branch on GitHub contains one or more commits per criterion, and the latest push is green.
- No secrets committed (verified by reviewing `git diff --cached` before each commit); `.env` is git-ignored; no password appears in chat, logs, or test output.

## 10. Assumptions log

Agents append decisions here when requirements were ambiguous (date, decision, reason).

- Vehicles are admin-managed; users are renters (see section 2).
- Single-tenant, single currency, no taxes/deposits/late fees.
- Soft delete for vehicles, deactivate (not delete) for users with history.

- 2026-11-21: `GET /health` is served at `/api/v1/health` (under the base path). Reason: section 4 sets base path `/api/v1` for all routes.
- 2026-11-21: The session dependency commits after the route returns, so services call `session.flush()` where a DB constraint violation must become a `409`. Reason: FastAPI runs post-`yield` code after the response is built.
- 2026-11-21: Dev dependency `httpx2` replaces `httpx` (Starlette's TestClient deprecates `httpx`).
- 2026-11-21: Case-insensitive email uniqueness uses a unique index on `lower(email)` (no `citext`), because the init script only installs `btree_gist`.
- 2026-11-21: Alembic gets its database URL from `.env` via `app.db.get_engine`, never from `alembic.ini`. The test suite resets `vehicles_test` and migrates it to head once per session.
- 2026-11-21: Validation errors (422) are wrapped in the same envelope as `{"error": {"code": "validation_error", "message": ..., "details": [{loc, msg, type}]}}`. Submitted input is never echoed, since it may hold passwords.
- 2026-11-21: Wrong `current_password` on a password change returns `403` (`invalid_current_password`); a missing `current_password` returns `422`. Reason: the caller is authenticated, so `401` would imply a bad token.
- 2026-11-21: `PATCH /users/me` accepts `role`/`is_active` in the schema only to refuse them with `403` (also for admins, per 6.3); any other unknown field is `422`. A refused request applies none of its changes.
- 2026-11-21: Passwords are limited to 12-128 characters (upper bound guards argon2 against oversized input).
- 2026-11-21: The last-active-admin rule (6.3) is enforced for any target user, not only the caller: no request may leave the system without an active admin (`409`, code `last_admin`). The active admins are locked with `FOR UPDATE` during the check.
- 2026-11-21: Admins may reset another user's password via `PATCH /users/{id}` without `current_password`.
- 2026-11-21: `DELETE /users/{id}` for a user whose rentals are all `completed`/`cancelled` returns `409` (`user_has_rental_history`) rather than silently deactivating; the admin deactivates via `PATCH`. Reason: a `204` that does not delete would be surprising, and section 6.2 allows hard delete only without rental history.
- 2026-11-21: `create-admin` never modifies an existing user. If `ADMIN_EMAIL` belongs to a user who is not an active admin it exits `1` with a message, instead of promoting or reactivating that account. It prints neither the email nor the password.
- 2026-11-21: VINs, when given, must be 17 characters (A-Z without I/O/Q, and digits) and are stored uppercase. `daily_rate` accepts at most 8 digits with 2 decimals and is serialised as a string (e.g. `"49.90"`) to avoid float rounding.
- 2026-11-21: `available_from`/`available_to` return only vehicles with status `available` and no `reserved`/`active` rental overlapping the inclusive range; giving one bound means a single day, and `from > to` is `422`. `make` filter is a case-insensitive exact match.
- 2026-11-21: Rentals are limited to 365 days (`422`, code `invalid_dates`) and `total_price` must fit `Numeric(10, 2)`; "today" is the UTC date. Sending `total_price`, `status` or any other unknown field on create is `422`.
- 2026-11-21: An admin creating a rental for a user who does not exist gets `404`; for a deactivated user `409` (`user_inactive`). Authorization (`403`) is checked before vehicle lookup (`404`).
- 2026-11-21: For non-admins the `user_id` filter on `GET /rentals` is applied on top of the ownership scope, so another user's id yields an empty page rather than an error.
- 2026-11-21: `PATCH /rentals/{id}` edits only `start_date`, `end_date` and `notes`. Users: own rental, only while `reserved` (else `409` `invalid_state`). Admins: any rental; dates change only while `reserved`/`active`, notes at any status. A date edit recomputes `total_price` from the daily rate frozen at creation (`total_price / days`), not the vehicle's current rate. A user may not move `start_date` into the past (admins may).
- 2026-11-21: Section 4 only lists `POST /rentals/{id}/cancel`, but the state machine in 6.5 needs a way to reach `active` and `completed`. Added two admin-only endpoints that mirror it: `POST /rentals/{id}/activate` (`reserved -> active`) and `POST /rentals/{id}/complete` (`active -> completed`). Users get `403` on them (section 2: users can only cancel). This is additive; no listed endpoint changed.
- 2026-11-21: Section 6.6 operational settings are optional env vars: `CORS_ORIGINS` (comma-separated; CORS is off when unset) and `DOCS_ENABLED` (default `true`; `false` removes `/docs`, `/redoc` and `/openapi.json`). Every response carries `X-Request-ID` (a valid inbound value is echoed, otherwise one is generated). Access logs have one line per request with method, path, status and duration, and never include query strings, bodies or credentials.

