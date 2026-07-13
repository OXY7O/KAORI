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

COPY frontend ./frontend
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js

RUN mkdir -p app/static/css \
    && npm run build-css


FROM base AS production

RUN groupadd --system kaori \
    && useradd --system --gid kaori --create-home --home-dir /app kaori

COPY --chown=kaori:kaori . /app
COPY --from=frontend-build --chown=kaori:kaori \
    /build/app/static/css/output.css \
    /app/app/static/css/output.css

RUN mkdir -p \
        /app/instance \
        /app/instance/report-render-staging \
        /app/instance/report-download-cache \
        /app/instance/archive-download-cache \
        /app/instance/archive-staging \
        /app/instance/celery-beat \
    && chown -R kaori:kaori /app/instance

USER kaori

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "run:app"]
