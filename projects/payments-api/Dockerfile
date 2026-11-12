# syntax=docker/dockerfile:1

# Images are pinned by digest so builds are reproducible and can't be changed
# under us. Dependabot proposes digest updates.
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml uv.lock ./
# Install exactly what uv.lock records: pinned versions, verified by hash,
# wheels only (no build scripts run). uv is only used here, not shipped.
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    uv export --locked --no-dev --no-emit-project --no-header --quiet -o requirements.txt \
 && pip install --no-cache-dir --require-hashes --no-deps --only-binary=:all: \
      --target /build/deps -r requirements.txt

FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS runtime
LABEL org.opencontainers.image.title="payments-api" \
      org.opencontainers.image.source="https://github.com/harshithkonatham/devops-ai-toolkit"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/deps:/app/src \
    DATABASE_PATH=/data/payments.db

# Debian security fixes land before the base image is rebuilt, so apply them here. pip is
# removed because dependencies were installed in the deps stage; at runtime it is unused.
RUN apt-get update \
 && apt-get -y upgrade --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall --yes --root-user-action=ignore pip \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data && chown app:app /data

WORKDIR /app
COPY --from=deps /build/deps /app/deps
COPY src /app/src

USER 10001:10001
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

ENTRYPOINT ["python", "-m", "uvicorn", "--factory", "payments_api.main:create_app", \
            "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-access-log"]
