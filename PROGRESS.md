# PROGRESS.md

Plan for `docs/PROJECT.md` section 8. One or more Conventional Commits per criterion;
each is done only when `ruff check . && ruff format --check . && mypy app && pytest -q` is green.

Branch: `feature/vehicle-management-backend`

| ID | Summary | Status |
|----|---------|--------|
| AC-F0 | Secrets handling, `.env.example`, `check-env` | done |
| AC-F1 | Scaffold, config, `/health`, test DB wiring | done |
| AC-F2 | Alembic + initial migration | done |
| AC-F3 | Error envelope + handlers | done |
| AC-A1 | `POST /auth/login` | done |
| AC-A2 | Token auth dependencies, DB re-check | done |
| AC-U1 | `/users/me` | done |
| AC-U2 | Admin create user | done |
| AC-U3 | Admin list/get users | pending |
| AC-U4 | Admin update user | pending |
| AC-U5 | Admin delete user | pending |
| AC-U6 | CLI `create-admin` | pending |
| AC-V1 | Create vehicle | pending |
| AC-V2 | List/get vehicles | pending |
| AC-V3 | Update vehicle | pending |
| AC-V4 | Soft-delete vehicle | pending |
| AC-R1 | Create rental | pending |
| AC-R2 | Overlap protection | pending |
| AC-R3 | List/get rentals | pending |
| AC-R4 | Update rental | pending |
| AC-R5 | Cancel and state machine | pending |
| AC-R6 | Admin delete rental | pending |
| AC-H1 | Permission matrix test | pending |
| AC-H2 | Fresh-clone gate, README | pending |
