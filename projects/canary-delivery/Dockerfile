# syntax=docker/dockerfile:1

# Pinned by digest so builds are reproducible. Dependabot proposes updates.
# The app has no third-party runtime dependencies, so one stage is enough.
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
LABEL org.opencontainers.image.title="canary-demo" \
      org.opencontainers.image.source="https://github.com/harshithkonatham/devops-ai-toolkit"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Debian security fixes land before the base image is rebuilt, so apply them here. The app
# has no third-party dependencies, so pip is never used and is removed.
RUN apt-get update \
 && apt-get -y upgrade --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall --yes --root-user-action=ignore pip \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY src /app/src

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

# The same image also runs the load generator (see deploy/k8s/loadgen.yaml).
ENTRYPOINT ["python", "-m"]
CMD ["canary_demo"]
