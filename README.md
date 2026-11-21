# vehix

Vehicle management backend: users, vehicles and rentals behind a JWT-secured REST API.

- Python 3.12+, FastAPI, Pydantic v2
- PostgreSQL 16, SQLAlchemy 2.x, Alembic
- Auth: JWT access tokens (PyJWT) and argon2 password hashing

Requirements live in [`docs/PROJECT.md`](docs/PROJECT.md). Contributor and agent rules are in
[`AGENTS.md`](AGENTS.md). Progress per acceptance criterion is in [`PROGRESS.md`](PROGRESS.md).

**Pick your path:**

- Changing the code? Follow [Development](#development).
- Running it for real users? Follow [Production deployment](#production-deployment).

| | Development | Production |
|---|---|---|
| PostgreSQL | Local Podman container from `db/Dockerfile` | Managed or self-hosted PostgreSQL 16 (the tested version), your own database and user |
| Settings | `.env` file in the repo root | Real environment variables or a locked-down env file |
| Dependencies | `requirements-dev.txt` | `requirements.txt` |
| Server | `uvicorn ... --reload` | `uvicorn` with workers behind a TLS reverse proxy |
| API docs (`/docs`) | On | Off (`DOCS_ENABLED=false`) |
| Test database | `vehicles_test` | Not used |

## Configuration reference

The app reads these from the process environment, or from `.env` in the repo root when the file
exists. A real environment variable wins over `.env`. The app, the CLI and the tests refuse to
start if a required variable is missing, empty or still `CHANGE_ME`, and they report variable
**names** only, never values.

| Variable | Required | Notes |
|----------|----------|-------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` | yes | Where the application database lives |
| `DB_PASSWORD` | yes | Database password |
| `JWT_SECRET` | yes | Signing key for access tokens. Use a long random value (at least 32 bytes) |
| `JWT_EXPIRE_MINUTES` | yes | Access token lifetime |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | yes | First admin, used by `create-admin`. The password must be 12-128 characters |
| `TEST_DB_NAME` | yes | Database the tests use. Production never uses it, but it must still be set to a real-looking value such as `vehicles_test` |
| `CORS_ORIGINS` | no | Comma-separated allowed browser origins. CORS is off when unset |
| `DOCS_ENABLED` | no | Default `true`. `false` removes `/docs`, `/redoc` and `/openapi.json` |

`python -m app.cli check-env` validates the configuration without printing any value.

## Development

Prerequisites: Podman and Python 3.12+. On macOS or Windows, run
`podman machine init && podman machine start` once.

### 1. Configure secrets

```bash
cp .env.example .env
$EDITOR .env             # replace every CHANGE_ME with your own value
git check-ignore .env    # must print ".env"
python -m app.cli check-env
```

`.env` is git-ignored. Never commit it or paste its values into chat, issues or logs.

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
It runs only on the first start of an empty volume.

> **Changing `DB_PASSWORD` later?** Postgres stores the password inside the volume, so editing
> `.env` alone makes logins fail with `password authentication failed`. Reset the local
> database (this deletes its data) and start it again:
> `podman rm -f vehicles-db && podman volume rm vehicles-pgdata`.

### 3. Install, migrate, run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli create-admin      # idempotent; uses ADMIN_EMAIL / ADMIN_PASSWORD
uvicorn app.main:app --reload
```

The API is served under `/api/v1`. Open `http://localhost:8000/docs` for the interactive docs.
Log in with `POST /api/v1/auth/login` and send the token as `Authorization: Bearer <token>`.

### 4. Quality gate

Run this before every commit. It needs the database from step 2.

```bash
ruff check . && ruff format --check . && mypy app && pytest -q
```

The tests use the separate `vehicles_test` database. They reset its schema and apply the
migrations at the start of each session, and they generate throwaway passwords at runtime.

## Production deployment

Do **not** reuse the development setup in production: `db/Dockerfile` publishes port 5432 and
creates a test database, `--reload` is for editing code, and `/docs` should not be public.

### What you need

- A Linux host or container platform with Python 3.12+ and `git`.
- A PostgreSQL database the app host can reach (managed service or your own server).
- A reverse proxy or load balancer that terminates HTTPS (Caddy, nginx, a cloud load balancer).
- A way to store secrets: your platform's secret store, or an env file readable only by the
  service user.

### 1. Prepare the database

Create a dedicated application user that is not a superuser, and a database it owns. Run these
as a database administrator. `\password` prompts for the password, so it never appears in a
command or in your shell history:

```sql
CREATE ROLE vehicles_app LOGIN;
\password vehicles_app
CREATE DATABASE vehicles OWNER vehicles_app;
```

The first migration runs `CREATE EXTENSION IF NOT EXISTS btree_gist`, which the rental
overlap constraint needs. `btree_gist` is a trusted extension, so the database owner may
create it. If your provider restricts extensions, have an administrator run it once in the
`vehicles` database before migrating.

Only the application host should be able to reach the database port. Do not expose it to the
internet.

### 2. Install the application

```bash
git clone https://github.com/abhilashmnair/vehix.git /opt/vehix
cd /opt/vehix
git checkout <release-tag-or-commit>      # deploy a specific version, not a moving branch
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # production dependencies only
```

### 3. Configure

Set the variables from the [configuration reference](#configuration-reference) through your
platform's secret store, or in an env file that only the service user can read (for example
`/etc/vehix/vehix.env`, owner = service user, mode `600`). There is no need to create a `.env`
file inside the repo.

Production values to set:

- `DB_HOST`, `DB_PORT`, `DB_USER=vehicles_app`, `DB_NAME=vehicles`, and the `DB_PASSWORD` you chose above.
- `JWT_SECRET`: a freshly generated random value, unique to production. For example, run
  `python -c "import secrets; print(secrets.token_urlsafe(48))"` and store the result straight
  in your secret store.
- `JWT_EXPIRE_MINUTES`: keep it short (the default of 30 is a sensible start).
- `ADMIN_EMAIL` and `ADMIN_PASSWORD`: your first admin. Use a strong, unique password.
- `DOCS_ENABLED=false`.
- `CORS_ORIGINS`: only the exact origins of your front end, if a browser app calls the API.
  Leave it unset if there is none.
- `TEST_DB_NAME`: required by the settings loader but never used. Set it to `vehicles_test`.

Check the result. This prints variable names only:

```bash
.venv/bin/python -m app.cli check-env
```

The `ADMIN_*` variables stay required for the app to start, even after the admin exists.

### 4. Create the schema and the first admin

Run these once per release, before starting the new version:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin
```

`create-admin` is safe to repeat. It never changes an existing user. After your first login,
change the admin password with `PATCH /api/v1/users/me` (it requires `current_password`).

### 5. Run the server

Bind to localhost and let the reverse proxy face the internet:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  --workers 2 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

Use roughly one worker per CPU core. Run it under a process manager so it starts on boot and
restarts on failure. Example systemd unit, `/etc/systemd/system/vehix.service`:

```ini
[Unit]
Description=vehix API
After=network.target

[Service]
User=vehix
WorkingDirectory=/opt/vehix
EnvironmentFile=/etc/vehix/vehix.env
ExecStart=/opt/vehix/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then `systemctl daemon-reload && systemctl enable --now vehix`. Adjust the user and paths to
your host. If you deploy with containers or another platform, run the same `uvicorn` command
and give it the same environment variables.

### 6. Put HTTPS in front

Terminate TLS at the reverse proxy and forward to `127.0.0.1:8000`. With Caddy, which obtains
certificates automatically, the whole config is:

```
api.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Never expose the uvicorn port or the database port directly.

### 7. Verify the deployment

```bash
curl -i https://api.example.com/api/v1/health      # 200, and an X-Request-ID header
curl -i https://api.example.com/docs               # 404, because docs are off
```

Then log in with `POST /api/v1/auth/login` using the admin you created. Use
`/api/v1/health` as the load balancer health check: it returns `200` when the database is
reachable and `503` when it is not.

### Operating it

- **Upgrade:** `git fetch && git checkout <new-tag>`, then `.venv/bin/pip install -r requirements.txt`,
  `.venv/bin/alembic upgrade head`, then restart the service. Take a database backup first.
- **Backups:** schedule `pg_dump` (or your provider's snapshots) and test a restore.
  To roll back a release, deploy the previous version and restore the backup taken before the
  upgrade. `alembic downgrade -1` exists but can drop data, so prefer the restore.
- **Logs:** one access line per request on stdout, tagged with the request ID. Queries,
  bodies, passwords and tokens are never logged. Ask users to quote the `X-Request-ID` header
  when reporting a problem.
- **Rotating `JWT_SECRET`:** change it and restart. Every issued token stops working and users
  must log in again.
- **Changing `DB_PASSWORD`:** change it in the database first (`ALTER ROLE ... PASSWORD`
  via `\password`), then update the secret and restart.

### Production checklist

- [ ] Application database user is not a superuser, and the database port is not public
- [ ] `JWT_SECRET`, `DB_PASSWORD` and `ADMIN_PASSWORD` are unique to production and stored in a secret store
- [ ] `DOCS_ENABLED=false`, and `CORS_ORIGINS` lists only your real front end
- [ ] The service runs as a non-root user and restarts on failure
- [ ] HTTPS terminates at the proxy, and only the proxy is public
- [ ] `alembic upgrade head` succeeded and `/api/v1/health` returns `200`
- [ ] Database backups run, and a restore has been tested

## Endpoints

| Area | Endpoints |
|------|-----------|
| Health | `GET /health` (no auth) |
| Auth | `POST /auth/login` (no auth) |
| Users | `GET/PATCH /users/me`; admin: `GET/POST /users`, `GET/PATCH/DELETE /users/{id}` |
| Vehicles | `GET /vehicles`, `GET /vehicles/{id}`; admin: `POST /vehicles`, `PATCH/DELETE /vehicles/{id}` |
| Rentals | `GET/POST /rentals`, `GET/PATCH /rentals/{id}`, `POST /rentals/{id}/cancel`; admin: `DELETE /rentals/{id}`, `POST /rentals/{id}/activate`, `POST /rentals/{id}/complete` |

All paths are under `/api/v1`. `activate` (`reserved -> active`) and `complete`
(`active -> completed`) are admin-only additions that the rental state machine needs. See the
assumptions log in `docs/PROJECT.md`, section 10.

Every response carries an `X-Request-ID` header, and access logs include it.
Errors use one envelope: `{"error": {"code": ..., "message": ..., "details": ...}}`, where
`details` appears only for validation errors.
