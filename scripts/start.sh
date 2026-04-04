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

try_install_package() {
  local pkg="$1"
  log "Trying package: $pkg"
  apt_update_once
  if as_root apt-get install -y "$pkg"; then
    return 0
  fi
  return 1
}

ensure_compose_available() {
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    return
  fi

  if try_install_package docker-compose-plugin; then
    return
  fi

  if try_install_package docker-compose-v2; then
    return
  fi

  if try_install_package docker-compose; then
    return
  fi

  log "Failed to install Docker Compose. Install it manually and rerun start.sh"
  exit 1
}

ensure_prerequisites() {
  if [[ ! -f /etc/debian_version ]]; then
    log "Auto-install is supported for Debian/Ubuntu only. Install Docker manually."
    return
  fi

  ensure_package ca-certificates
  ensure_package curl
  ensure_package docker.io
  ensure_compose_available

  as_root systemctl enable docker >/dev/null 2>&1 || true
  as_root systemctl start docker >/dev/null 2>&1 || true
}

generate_secret_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi

  # Fallback when openssl is unavailable.
  date +%s%N
}

ensure_env_file() {
  if [[ -f "$REPO_ROOT/.env" ]]; then
    return
  fi

  local secret_key
  secret_key="$(generate_secret_key)"

  log "Missing .env file, creating a default working .env"
  cat > "$REPO_ROOT/.env" <<EOF
SECRET_KEY=${secret_key}
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
RAG_LLM_PROVIDER=gemini
RAG_GEMINI_MODEL=gemini-1.5-flash
RAG_CLAUDE_MODEL=claude-3-5-sonnet-20240620
RAG_EMBEDDING_PROVIDER=gemini
RAG_GEMINI_EMBEDDING_MODEL=models/embedding-001
RAG_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
CORS_ALLOW_ORIGINS=http://localhost:8501,http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173
DATABASE_URL=postgresql://hackathon:hackathon@db:5432/hackathon
DB_DATA_DIR=${REPO_ROOT}/runtime-data/postgres
CHROMA_DATA_DIR=${REPO_ROOT}/runtime-data/chroma
APP_DATA_DIR=${REPO_ROOT}/runtime-data/app
EOF
}

normalize_project_layout() {
  # Common zip variant: backend-cpp instead of backend_cpp
  if [[ ! -e "$REPO_ROOT/backend_cpp" && -d "$REPO_ROOT/backend-cpp" ]]; then
    log "Detected backend-cpp folder, creating compatibility symlink backend_cpp -> backend-cpp"
    ln -s "backend-cpp" "$REPO_ROOT/backend_cpp"
  fi

  # Optional compatibility for html frontend naming.
  if [[ ! -e "$REPO_ROOT/front" && -d "$REPO_ROOT/frontend_html" ]]; then
    log "Detected frontend_html folder, creating compatibility symlink front -> frontend_html"
    ln -s "frontend_html" "$REPO_ROOT/front"
  fi
}

ensure_cpp_dockerfile() {
  local target="$REPO_ROOT/backend_cpp/Dockerfile"
  if [[ -s "$target" ]]; then
    return
  fi

  local candidates=(
    "$REPO_ROOT/backend_cpp/dockerfile"
    "$REPO_ROOT/backend_cpp/DockerFile"
    "$REPO_ROOT/backend-cpp/Dockerfile"
    "$REPO_ROOT/backend-cpp/dockerfile"
    "$REPO_ROOT/backend-cpp/DockerFile"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -s "$candidate" ]]; then
      log "Recovering backend_cpp/Dockerfile from: $candidate"
      cp "$candidate" "$target"
      return
    fi
  done

  if [[ -d "$REPO_ROOT/backend_cpp" && -s "$REPO_ROOT/backend_cpp/CMakeLists.txt" && -s "$REPO_ROOT/backend_cpp/main.cpp" ]]; then
    log "backend_cpp/Dockerfile missing, generating fallback Dockerfile"
    cat > "$target" <<'EOF'
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN cmake . && make

EXPOSE 8080

CMD ["./cpp_backend"]
EOF
  fi
}

ensure_required_files() {
  local required_files=(
    "$REPO_ROOT/docker-compose.yml"
    "$REPO_ROOT/backend_cpp/Dockerfile"
    "$REPO_ROOT/backend_python/Dockerfile"
    "$REPO_ROOT/frontend_python/Dockerfile"
    "$REPO_ROOT/front/Dockerfile"
    "$REPO_ROOT/front/nginx.conf"
  )

  local missing=0
  for file_path in "${required_files[@]}"; do
    if [[ ! -s "$file_path" ]]; then
      log "Missing or empty required file: $file_path"
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    log "Project files look incomplete. Re-upload full zip and rerun start.sh"
    exit 1
  fi
}

cleanup_container_name_conflicts() {
  # docker-compose.yml uses fixed container names; remove stale containers with those names.
  local fixed_names=(
    hackathon_db
    hackathon_vector_db
    hackathon_cpp
    hackathon_python
    hackathon_frontend
    hackathon_web
  )

  local has_conflicts=0
  for name in "${fixed_names[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -Fxq "$name"; then
      has_conflicts=1
      log "Removing conflicting container name: $name"
      docker rm -f "$name" >/dev/null 2>&1 || true
    fi
  done

  if [[ "$has_conflicts" -eq 1 ]]; then
    log "Container name conflicts cleared"
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

ensure_prerequisites
require_cmd docker
ensure_env_file
normalize_project_layout
ensure_cpp_dockerfile
ensure_required_files
cleanup_container_name_conflicts

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
