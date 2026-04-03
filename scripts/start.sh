#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() {
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi

  log "docker compose is not available"
  exit 1
}

require_cmd docker

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  log "Missing .env file"
  log "Create it from template: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env"
set +a

DB_DIR="${DB_DATA_DIR:-$REPO_ROOT/runtime-data/postgres}"
CHROMA_DIR="${CHROMA_DATA_DIR:-$REPO_ROOT/runtime-data/chroma}"
APP_DIR="${APP_DATA_DIR:-$REPO_ROOT/runtime-data/app}"
mkdir -p "$DB_DIR" "$CHROMA_DIR" "$APP_DIR"

log "Starting containers"
compose_cmd up -d --build --remove-orphans

log "Done"
compose_cmd ps
