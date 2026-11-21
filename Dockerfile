# Production image for the vehix API. (The database image for local development is db/Dockerfile.)
#
# Build (--format docker keeps the HEALTHCHECK below; Podman's default OCI format drops it):
#   podman build --format docker -t vehix-api .
#
# Settings and secrets are NOT baked in; pass them as environment variables at run time
# (see README, "Production deployment"). Run migrations with the same image:
#   podman run --rm --env-file <your-env-file> vehix-api alembic upgrade head
#
# Fully qualified image name so Podman does not prompt for a registry.
FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Production dependencies only; copied first so this layer is cached between code changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as an unprivileged user.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin vehix
USER vehix

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

# Behind a reverse proxy: set FORWARDED_ALLOW_IPS to the proxy's address if it is not 127.0.0.1.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
