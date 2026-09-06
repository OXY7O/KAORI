# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12-slim-bookworm AS ci

ARG PIP_VERSION=26.2.1
ARG ACTIONLINT_VERSION=1.7.12
ARG GITLEAKS_VERSION=8.30.1
ARG HADOLINT_VERSION=2.15.1
ARG TRIVY_VERSION=0.74.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/tmp

WORKDIR /workspace

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

# CI system packages intentionally follow Bookworm repository patch levels.
# hadolint ignore=DL3008
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        jq \
        libcairo2 \
        libcairo2-dev \
        libffi-dev \
        libgdk-pixbuf-2.0-0 \
        libgdk-pixbuf-2.0-dev \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpango1.0-dev \
        libpangoft2-1.0-0 \
        libpq-dev \
        libpq5 \
        pkg-config \
        postgresql-client \
        redis-tools \
        shared-mime-info \
        shellcheck \
        tar \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements /tmp/kaori-requirements
COPY .github/ci/requirements-security.txt /tmp/requirements-security.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install "pip==${PIP_VERSION}" \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/kaori-requirements/dev.txt \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements-security.txt

RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) action_asset_arch='amd64'; gitleaks_arch='x64'; trivy_arch='64bit'; hadolint_arch='x86_64' ;; \
        arm64) action_asset_arch='arm64'; gitleaks_arch='arm64'; trivy_arch='ARM64'; hadolint_arch='arm64' ;; \
        *) echo "Unsupported CI toolchain architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/actionlint.tar.gz "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${action_asset_arch}.tar.gz"; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/actionlint-checksums.txt "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_checksums.txt"; \
    grep " actionlint_${ACTIONLINT_VERSION}_linux_${action_asset_arch}.tar.gz$" /tmp/actionlint-checksums.txt \
      | sed "s#actionlint_${ACTIONLINT_VERSION}_linux_${action_asset_arch}.tar.gz#/tmp/actionlint.tar.gz#" \
      | sha256sum -c -; \
    tar -xzf /tmp/actionlint.tar.gz -C /tmp actionlint; \
    install -m 0755 /tmp/actionlint /usr/local/bin/actionlint; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/gitleaks.tar.gz "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${gitleaks_arch}.tar.gz"; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/gitleaks-checksums.txt "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_checksums.txt"; \
    grep " gitleaks_${GITLEAKS_VERSION}_linux_${gitleaks_arch}.tar.gz$" /tmp/gitleaks-checksums.txt \
      | sed "s#gitleaks_${GITLEAKS_VERSION}_linux_${gitleaks_arch}.tar.gz#/tmp/gitleaks.tar.gz#" \
      | sha256sum -c -; \
    tar -xzf /tmp/gitleaks.tar.gz -C /tmp gitleaks; \
    install -m 0755 /tmp/gitleaks /usr/local/bin/gitleaks; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/hadolint "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-linux-${hadolint_arch}"; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/hadolint-checksums.txt "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/checksums.sha256"; \
    hadolint_checksum="$(awk -v asset="*hadolint-linux-${hadolint_arch}" '$2 == asset {print $1}' /tmp/hadolint-checksums.txt)"; \
    test -n "$hadolint_checksum"; \
    printf '%s  %s\n' "$hadolint_checksum" /tmp/hadolint | sha256sum -c -; \
    install -m 0755 /tmp/hadolint /usr/local/bin/hadolint; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/trivy.tar.gz "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz"; \
    curl --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 180 -fsSLo /tmp/trivy-checksums.txt "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_checksums.txt"; \
    grep " trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz$" /tmp/trivy-checksums.txt \
      | sed "s#trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz#/tmp/trivy.tar.gz#" \
      | sha256sum -c -; \
    tar -xzf /tmp/trivy.tar.gz -C /tmp trivy; \
    install -m 0755 /tmp/trivy /usr/local/bin/trivy; \
    rm -f /tmp/actionlint* /tmp/gitleaks* /tmp/hadolint* /tmp/trivy*

CMD ["bash"]
