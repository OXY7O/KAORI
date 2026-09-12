# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base

ARG PIP_VERSION=26.2.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Debian package patch levels intentionally follow Bookworm repositories.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade libpcre2-8-0 \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt /tmp/requirements/base.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install "pip==${PIP_VERSION}" \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements/base.txt \
    && rm -f /tmp/requirements/base.txt

COPY docker/entrypoint.sh /usr/local/bin/kaori-entrypoint
RUN chmod 0755 /usr/local/bin/kaori-entrypoint

ENTRYPOINT ["kaori-entrypoint"]

FROM node:24.14.0-bookworm-slim AS frontend-build

WORKDIR /build

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY frontend ./frontend
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js
COPY scripts/verify_css_build.mjs scripts/vendor_frontend_assets.mjs ./scripts/

RUN npm run build-frontend \
    && npm run verify-frontend

FROM base AS development

COPY requirements/dev.txt /tmp/requirements/dev.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements/dev.txt \
    && rm -f /tmp/requirements/dev.txt

COPY . /app

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

FROM base AS production

ARG VCS_REF=""
ARG BUILD_DATE=""
ARG VERSION="dev"

LABEL org.opencontainers.image.source="https://github.com/OXY7O/KAORI" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="KAORI" \
      org.opencontainers.image.description="Knowledge, Automation, Operations, Resilience & Intelligence"

COPY --from=frontend-build --chown=kaori:kaori /build/app/static/css/output.css /app/app/static/css/output.css
COPY --from=frontend-build --chown=kaori:kaori /build/app/static/vendor /app/app/static/vendor

RUN groupadd --system --gid 10001 kaori \
    && useradd --system --uid 10001 --gid kaori --home-dir /app --shell /usr/sbin/nologin kaori

COPY --chown=kaori:kaori app /app/app
COPY --chown=kaori:kaori migrations /app/migrations
COPY --chown=kaori:kaori run.py celery_worker.py gunicorn.conf.py /app/
COPY --chown=kaori:kaori \
    scripts/wait_for_db.py \
    scripts/validate_production_env.py \
    /app/scripts/
COPY --chown=kaori:kaori alembic.ini /app/alembic.ini

RUN rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
    && python -m pip --version >/dev/null 2>&1 && exit 1 || true \
    && find /usr/local/lib/python3.12/site-packages -type d -name '__pycache__' -prune -exec rm -rf {} + \
    && find /usr/local/lib/python3.12/site-packages -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete \
    && chown -R kaori:kaori /app

USER kaori

EXPOSE 8000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]
