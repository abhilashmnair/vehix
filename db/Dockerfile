# Local PostgreSQL for development, built and run with Podman.
#
# Build:
#   podman build -t vehicles-db -f db/Dockerfile db/
#
# Run (rootless Podman works; data persisted in a named volume).
# The password comes from .env (DB_PASSWORD); never hardcode it here or on the command line:
#   set -a; . ./.env; set +a
#   podman volume create vehicles-pgdata
#   POSTGRES_PASSWORD="$DB_PASSWORD" podman run -d --name vehicles-db \
#     -p 5432:5432 \
#     -e POSTGRES_PASSWORD \
#     -v vehicles-pgdata:/var/lib/postgresql/data \
#     vehicles-db
#
# Reset:
#   podman rm -f vehicles-db && podman volume rm vehicles-pgdata
#
# Note: the init script below runs ONLY on the first start with an empty data volume.

# Fully qualified image name so Podman does not prompt for a registry.
FROM docker.io/library/postgres:16

ENV POSTGRES_USER=postgres \
    POSTGRES_DB=vehicles

# Creates the test database and enables btree_gist (needed for the rental
# overlap exclusion constraint) in both the dev and test databases.
RUN printf '%s\n' \
  '#!/bin/bash' \
  'set -e' \
  'psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE vehicles_test;"' \
  'for db in "$POSTGRES_DB" vehicles_test; do' \
  '  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"' \
  'done' \
  > /docker-entrypoint-initdb.d/01-init.sh \
  && chmod +x /docker-entrypoint-initdb.d/01-init.sh

EXPOSE 5432

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
