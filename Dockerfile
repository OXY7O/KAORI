# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
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

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements/base.txt

COPY docker/entrypoint.sh /usr/local/bin/kaori-entrypoint
RUN chmod 0755 /usr/local/bin/kaori-entrypoint

ENTRYPOINT ["kaori-entrypoint"]


FROM base AS development

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        curl \
        git \
        openssh-client \
        postgresql-client \
        redis-tools \
        sudo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/dev.txt /tmp/requirements/dev.txt
RUN python -m pip install -r /tmp/requirements/dev.txt

RUN useradd --create-home --uid 1000 --shell /bin/bash vscode \
    && echo "vscode ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && mkdir -p /workspace/kaori \
    && chown -R vscode:vscode /workspace

WORKDIR /workspace/kaori
USER vscode

CMD ["sleep", "infinity"]


FROM node:22-alpine AS frontend-build

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY scripts/vendor_frontend_assets.mjs \
    scripts/verify_frontend_assets.mjs \
    scripts/verify_css_build.mjs \
    ./scripts/
COPY frontend ./frontend
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js
COPY app/static/vendor/cytoscape ./app/static/vendor/cytoscape

RUN mkdir -p app/static/css app/static/vendor app/static/fonts \
    && npm run build-frontend \
    && npm run verify-frontend


FROM base AS production

RUN groupadd --system kaori \
    && useradd --system --gid kaori --create-home --home-dir /app kaori

COPY --chown=kaori:kaori . /app
COPY --from=frontend-build --chown=kaori:kaori \
    /build/app/static/css/output.css \
    /app/app/static/css/output.css
COPY --from=frontend-build --chown=kaori:kaori \
    /build/app/static/vendor \
    /app/app/static/vendor
COPY --from=frontend-build --chown=kaori:kaori \
    /build/app/static/fonts \
    /app/app/static/fonts

RUN mkdir -p \
        /app/instance \
        /app/instance/report-render-staging \
        /app/instance/report-download-cache \
        /app/instance/archive-download-cache \
        /app/instance/archive-staging \
        /app/instance/celery-beat \
    && chown -R kaori:kaori /app/instance

RUN python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.12/ensurepip /root/.cache/pip \
    && ! python -c 'import pip' >/dev/null 2>&1 \
    && ! python -c 'import ensurepip' >/dev/null 2>&1

USER kaori

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]
