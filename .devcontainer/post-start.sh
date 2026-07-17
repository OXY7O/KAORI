#!/usr/bin/env bash
set -Eeuo pipefail

cd /workspace/kaori
bash .devcontainer/ensure-frontend.sh
