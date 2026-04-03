#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

APT_UPDATED=0

log() {
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    log "Need root privileges. Run as root or install sudo."
    exit 1
  fi
}

apt_update_once() {
  if [[ "$APT_UPDATED" -eq 0 ]]; then
    as_root apt-get update
    APT_UPDATED=1
  fi
}

ensure_package() {
  local pkg="$1"
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    log "Installing package: $pkg"
    apt_update_once
    as_root apt-get install -y "$pkg"
  fi
}

ensure_prerequisites() {
  if [[ ! -f /etc/debian_version ]]; then
    log "Auto-install is supported for Debian/Ubuntu only. Install Docker manually."
    return
  fi

  ensure_package ca-certificates
  ensure_package curl
  ensure_package docker.io

  if ! docker compose version >/dev/null 2>&1; then
    ensure_package docker-compose-plugin
  fi

  as_root systemctl enable docker >/dev/null 2>&1 || true
  as_root systemctl start docker >/dev/null 2>&1 || true
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

ensure_prerequisites
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
