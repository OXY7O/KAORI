#!/usr/bin/env bash
# Generic Linux bootstrap for a dedicated GitHub Actions self-hosted runner host.
#
# Host contract:
#   - Linux (x86_64/amd64 or aarch64/arm64)
#   - systemd
#   - Docker Engine + Buildx
#   - basic GitHub Actions runner prerequisites
#
# Application runtimes such as Python, Node.js, PostgreSQL, and Redis are
# intentionally NOT installed here. KAORI CI jobs will run those in containers.
#
# This script intentionally DOES NOT register the runner with GitHub.
# DO NOT register with a repository token from this bootstrap script.

set -Eeuo pipefail

SCRIPT_NAME="$(basename "$0")"
RUNNER_USER="${RUNNER_USER:-github-runner}"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
RUNNER_VERSION="${RUNNER_VERSION:-latest}"
VERIFY_ONLY=false
SKIP_RUNNER_DOWNLOAD=false
SKIP_DOCKER_SMOKE=false

log() {
    printf '[runner-bootstrap] %s\n' "$*"
}

warn() {
    printf '[runner-bootstrap] WARNING: %s\n' "$*" >&2
}

fail() {
    printf '[runner-bootstrap] ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<USAGE
Usage: sudo ./${SCRIPT_NAME} [options]

Options:
  --runner-user USER        Runner service account (default: github-runner)
  --runner-dir PATH         Runner installation directory (default: /opt/actions-runner)
  --runner-version VERSION  Runner version without leading v, or latest (default: latest)
  --skip-runner-download    Install host prerequisites only
  --skip-docker-smoke       Skip the hello-world container smoke test
  --verify-only             Make no changes; validate an already-provisioned host
  -h, --help                Show this help

Environment equivalents:
  RUNNER_USER, RUNNER_DIR, RUNNER_VERSION
USAGE
}

while (($#)); do
    case "$1" in
        --runner-user)
            [[ $# -ge 2 ]] || fail '--runner-user requires a value.'
            RUNNER_USER="$2"
            shift 2
            ;;
        --runner-dir)
            [[ $# -ge 2 ]] || fail '--runner-dir requires a value.'
            RUNNER_DIR="$2"
            shift 2
            ;;
        --runner-version)
            [[ $# -ge 2 ]] || fail '--runner-version requires a value.'
            RUNNER_VERSION="$2"
            shift 2
            ;;
        --skip-runner-download)
            SKIP_RUNNER_DOWNLOAD=true
            shift
            ;;
        --skip-docker-smoke)
            SKIP_DOCKER_SMOKE=true
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

[[ "$(uname -s)" == 'Linux' ]] || fail 'This bootstrap supports Linux hosts only.'
[[ -r /etc/os-release ]] || fail '/etc/os-release is required.'
# shellcheck disable=SC1091
source /etc/os-release

case "$(uname -m)" in
    x86_64|amd64)
        RUNNER_ARCH='x64'
        ;;
    aarch64|arm64)
        RUNNER_ARCH='arm64'
        ;;
    *)
        fail "Unsupported CPU architecture: $(uname -m). Use x86_64/amd64 or arm64/aarch64."
        ;;
esac

PACKAGE_FAMILY='unknown'
if command -v apt-get >/dev/null 2>&1; then
    PACKAGE_FAMILY='apt'
elif command -v dnf >/dev/null 2>&1; then
    PACKAGE_FAMILY='dnf'
fi

require_root() {
    if [[ "$VERIFY_ONLY" == false && "${EUID}" -ne 0 ]]; then
        fail "Installation mode must run as root. Use: sudo ./${SCRIPT_NAME}"
    fi
}

install_base_packages() {
    case "$PACKAGE_FAMILY" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update
            apt-get install -y --no-install-recommends \
                ca-certificates curl git jq tar gzip unzip xz-utils gnupg sudo \
                coreutils findutils procps util-linux
            ;;
        dnf)
            dnf install -y \
                ca-certificates curl git jq tar gzip unzip xz sudo \
                coreutils findutils procps-ng util-linux dnf-plugins-core shadow-utils
            ;;
        *)
            fail 'Unsupported package manager. Install Docker, Git, curl, jq, tar, gzip, unzip, sudo, and CA certificates manually, then rerun with --verify-only.'
            ;;
    esac
}

configure_docker_apt_repo() {
    local repo_os suite arch

    case "${ID:-}" in
        ubuntu)
            repo_os='ubuntu'
            suite="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
            ;;
        debian)
            repo_os='debian'
            suite="${VERSION_CODENAME:-}"
            ;;
        *)
            fail "Automatic Docker repository setup is not supported for apt distro '${ID:-unknown}'. Install Docker Engine manually from the vendor-supported repository and rerun this script."
            ;;
    esac

    [[ -n "$suite" ]] || fail 'Unable to resolve apt distribution codename for Docker repository.'
    arch="$(dpkg --print-architecture)"

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${repo_os}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    cat > /etc/apt/sources.list.d/docker.sources <<APT_REPO
Types: deb
URIs: https://download.docker.com/linux/${repo_os}
Suites: ${suite}
Components: stable
Architectures: ${arch}
Signed-By: /etc/apt/keyrings/docker.asc
APT_REPO

    apt-get update
}

configure_docker_dnf_repo() {
    local repo_os

    case "${ID:-}" in
        rhel|rocky|almalinux|ol)
            # Rocky/Alma/Oracle Linux are treated as RHEL-compatible for the
            # Docker CE repository. Docker only guarantees support for its
            # explicitly documented platforms, so verify after installation.
            repo_os='rhel'
            ;;
        centos)
            repo_os='centos'
            ;;
        fedora)
            repo_os='fedora'
            ;;
        *)
            if [[ "${ID_LIKE:-}" == *rhel* || "${ID_LIKE:-}" == *fedora* ]]; then
                repo_os='rhel'
                warn "Mapping distro '${ID:-unknown}' to Docker's RHEL repository because ID_LIKE='${ID_LIKE:-}'."
            else
                fail "Automatic Docker repository setup is not supported for dnf distro '${ID:-unknown}'. Install Docker Engine manually and rerun this script."
            fi
            ;;
    esac

    dnf config-manager --add-repo "https://download.docker.com/linux/${repo_os}/docker-ce.repo"
}

install_docker() {
    if command -v docker >/dev/null 2>&1; then
        log "Docker CLI already present: $(docker --version)"
    else
        log 'Installing Docker Engine from Docker official packages...'
        case "$PACKAGE_FAMILY" in
            apt)
                configure_docker_apt_repo
                apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                ;;
            dnf)
                configure_docker_dnf_repo
                dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                ;;
            *)
                fail 'Docker is not installed and this package manager is unsupported.'
                ;;
        esac
    fi

    if ! docker buildx version >/dev/null 2>&1; then
        warn 'Docker Buildx is missing; attempting to install docker-buildx-plugin.'
        case "$PACKAGE_FAMILY" in
            apt)
                apt-get install -y docker-buildx-plugin
                ;;
            dnf)
                dnf install -y docker-buildx-plugin
                ;;
            *)
                fail 'Docker Buildx is required but could not be installed automatically.'
                ;;
        esac
    fi

    command -v systemctl >/dev/null 2>&1 || fail 'systemd/systemctl is required for the dedicated runner host design.'
    systemctl enable --now docker
}

create_runner_user() {
    if id "$RUNNER_USER" >/dev/null 2>&1; then
        log "Runner user already exists: ${RUNNER_USER}"
    else
        useradd --system --create-home --home-dir "/home/${RUNNER_USER}" --shell /bin/bash "$RUNNER_USER"
        log "Created runner user: ${RUNNER_USER}"
    fi

    getent group docker >/dev/null 2>&1 || groupadd docker
    usermod -aG docker "$RUNNER_USER"

    install -d -m 0755 -o "$RUNNER_USER" -g "$RUNNER_USER" "$RUNNER_DIR"
}

resolve_runner_release() {
    local release_json version asset_name asset_url digest tmp_tar actual_digest expected_digest

    release_json="$(mktemp)"
    tmp_tar="$(mktemp --suffix=.tar.gz)"
    trap 'rm -f "${release_json:-}" "${tmp_tar:-}"' RETURN

    if [[ "$RUNNER_VERSION" == 'latest' ]]; then
        curl -fsSL --retry 3 --retry-delay 2 \
            'https://api.github.com/repos/actions/runner/releases/latest' \
            -o "$release_json"
        version="$(jq -r '.tag_name // empty | ltrimstr("v")' "$release_json")"
    else
        version="${RUNNER_VERSION#v}"
        curl -fsSL --retry 3 --retry-delay 2 \
            "https://api.github.com/repos/actions/runner/releases/tags/v${version}" \
            -o "$release_json"
    fi

    [[ -n "$version" ]] || fail 'Unable to resolve GitHub Actions Runner version.'
    asset_name="actions-runner-linux-${RUNNER_ARCH}-${version}.tar.gz"
    asset_url="$(jq -r --arg name "$asset_name" '.assets[] | select(.name == $name) | .browser_download_url' "$release_json" | head -n1)"
    digest="$(jq -r --arg name "$asset_name" '.assets[] | select(.name == $name) | (.digest // empty)' "$release_json" | head -n1)"

    [[ -n "$asset_url" ]] || fail "Runner release asset not found: ${asset_name}"

    log "Downloading GitHub Actions Runner ${version} (${RUNNER_ARCH})..."
    curl -fL --retry 3 --retry-delay 2 "$asset_url" -o "$tmp_tar"

    if [[ "$digest" == sha256:* ]]; then
        expected_digest="${digest#sha256:}"
        actual_digest="$(sha256sum "$tmp_tar" | awk '{print $1}')"
        [[ "$actual_digest" == "$expected_digest" ]] || fail 'GitHub Actions Runner SHA-256 verification failed.'
        log 'Runner archive SHA-256 verified from GitHub release metadata.'
    else
        warn 'GitHub release metadata did not expose a SHA-256 digest; archive was downloaded over HTTPS but digest verification was skipped.'
    fi

    tar -xzf "$tmp_tar" -C "$RUNNER_DIR"
    printf '%s\n' "$version" > "${RUNNER_DIR}/.bootstrap-runner-version"
}

download_runner() {
    if [[ "$SKIP_RUNNER_DOWNLOAD" == true ]]; then
        log 'Skipping GitHub Actions Runner download by request.'
        return
    fi

    if [[ -f "${RUNNER_DIR}/.runner" ]]; then
        warn "${RUNNER_DIR} is already registered. Bootstrap will not overwrite a configured runner."
        return
    fi

    if [[ -x "${RUNNER_DIR}/bin/Runner.Listener" ]]; then
        log 'GitHub Actions Runner binaries already exist; leaving them unchanged.'
    else
        resolve_runner_release
    fi

    if [[ -x "${RUNNER_DIR}/bin/installdependencies.sh" ]]; then
        log 'Installing runner runtime dependencies using GitHub-provided dependency script...'
        "${RUNNER_DIR}/bin/installdependencies.sh"
    else
        fail "Runner dependency installer not found under ${RUNNER_DIR}/bin."
    fi

    chown -R "$RUNNER_USER:$RUNNER_USER" "$RUNNER_DIR"
}

check_memory() {
    local mem_kb swap_kb
    mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
    swap_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"

    if ((mem_kb < 3800000)); then
        warn "Host RAM is below ~4 GB ($(awk -v kb="$mem_kb" 'BEGIN {printf "%.1f GiB", kb/1024/1024}')). KAORI CI may experience memory pressure."
    fi
    if ((swap_kb == 0)); then
        warn 'No swap is configured. A small swap file is recommended as an OOM safety net on a 4 GB runner VM.'
    fi
}

verify_host() {
    local failed=0

    log "OS: ${PRETTY_NAME:-${ID:-unknown}}"
    log "Architecture: $(uname -m)"
    check_memory

    for cmd in git curl jq tar gzip docker; do
        if command -v "$cmd" >/dev/null 2>&1; then
            log "OK command: ${cmd}"
        else
            warn "Missing command: ${cmd}"
            failed=1
        fi
    done

    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            log 'OK Docker daemon is reachable.'
        else
            warn 'Docker CLI exists but the daemon is not reachable.'
            failed=1
        fi

        if docker buildx version >/dev/null 2>&1; then
            log "OK $(docker buildx version | head -n1)"
        else
            warn 'Docker Buildx is unavailable.'
            failed=1
        fi
    fi

    if id "$RUNNER_USER" >/dev/null 2>&1; then
        log "OK runner user exists: ${RUNNER_USER}"
        if id -nG "$RUNNER_USER" | tr ' ' '\n' | grep -qx docker; then
            log "OK ${RUNNER_USER} is a member of the docker group."
        else
            warn "${RUNNER_USER} is not in the docker group."
            failed=1
        fi

        if command -v sudo >/dev/null 2>&1 && sudo -u "$RUNNER_USER" -H docker info >/dev/null 2>&1; then
            log "OK ${RUNNER_USER} can access Docker."
        else
            warn "${RUNNER_USER} cannot access Docker yet. A fresh login/session may be required after group membership changes."
            failed=1
        fi
    else
        warn "Runner user does not exist: ${RUNNER_USER}"
        failed=1
    fi

    if [[ "$SKIP_RUNNER_DOWNLOAD" == false ]]; then
        if [[ -x "${RUNNER_DIR}/bin/Runner.Listener" && -x "${RUNNER_DIR}/config.sh" ]]; then
            log "OK GitHub Actions Runner binaries are present in ${RUNNER_DIR}."
        else
            warn "GitHub Actions Runner binaries are incomplete or absent in ${RUNNER_DIR}."
            failed=1
        fi
    fi

    if curl -fsS --connect-timeout 5 https://github.com/ >/dev/null 2>&1 \
        && curl -fsS --connect-timeout 5 https://api.github.com/ >/dev/null 2>&1; then
        log 'OK outbound HTTPS connectivity to github.com and api.github.com.'
    else
        warn 'GitHub HTTPS connectivity check failed.'
        failed=1
    fi

    if [[ "$VERIFY_ONLY" == false && "$SKIP_DOCKER_SMOKE" == false ]]; then
        if sudo -u "$RUNNER_USER" -H docker run --rm hello-world >/dev/null 2>&1; then
            log 'OK Docker container smoke test passed as runner user.'
        else
            warn 'Docker hello-world smoke test failed as runner user.'
            failed=1
        fi
    fi

    ((failed == 0)) || fail 'Host verification reported one or more failures.'
}

print_next_steps() {
    cat <<NEXT

[runner-bootstrap] Host preparation is complete.

Next steps (manual by design):
  1. In GitHub, open the target repository/organization Settings -> Actions -> Runners.
  2. Choose "New self-hosted runner" and generate the time-limited registration token.
  3. Configure the runner AS ${RUNNER_USER}, for example:

       sudo -u ${RUNNER_USER} -H bash -lc 'cd ${RUNNER_DIR} && ./config.sh --url <GITHUB_URL> --token <TIME_LIMITED_TOKEN> --name <RUNNER_NAME> --labels kaori-ci --unattended'

  4. After registration, install and start the service:

       cd ${RUNNER_DIR}
       sudo ./svc.sh install ${RUNNER_USER}
       sudo ./svc.sh start
       sudo ./svc.sh status

Security note:
  Membership in the docker group effectively grants root-equivalent control of
  the host. Keep this VM dedicated to trusted CI workloads and do not run
  untrusted pull-request code on it.
NEXT
}

main() {
    require_root

    if [[ "$VERIFY_ONLY" == true ]]; then
        log 'Running verification only; no host changes will be made.'
        verify_host
        log 'Verification completed successfully.'
        exit 0
    fi

    log "Detected OS: ${PRETTY_NAME:-${ID:-unknown}}"
    log "Package family: ${PACKAGE_FAMILY}"
    log "Runner user: ${RUNNER_USER}"
    log "Runner directory: ${RUNNER_DIR}"

    install_base_packages
    install_docker
    create_runner_user
    download_runner
    verify_host
    print_next_steps
}

main "$@"
