#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_dir="${repo_root}/api"
agent_dir="${repo_root}/agent"
web_dir="${repo_root}/web"

api_label="com.opencompute.api"
agent_label="com.opencompute.agent"
web_label="com.opencompute.web"

uv_bin="${UV_BIN:-$(command -v uv)}"
corepack_bin="${COREPACK_BIN:-$(command -v corepack)}"
node_bin="${NODE_BIN:-$(command -v node)}"
docker_bin="${DOCKER_BINARY:-$(command -v docker || true)}"
node_bin_dir="$(dirname "${node_bin}")"

agent_token="${PRIVATE_NODE_AGENT_TOKEN:-open-compute-agent-local-development-token}"
vllm_key="${VLLM_INTERNAL_API_KEY:-open-compute-vllm-local-development-key}"
database_url="sqlite+aiosqlite:////${api_dir#/}/open_compute_system.db"

remove_service() {
  launchctl remove "$1" >/dev/null 2>&1 || true
}

stop_all() {
  remove_service "${web_label}"
  remove_service "${api_label}"
  remove_service "${agent_label}"
}

check_port() {
  local port="$1"
  local owner
  owner="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${owner}" ]]; then
    echo "Port ${port} is already owned by PID ${owner}; refusing to replace it." >&2
    exit 1
  fi
}

wait_for_port_free() {
  local port="$1"
  local attempt
  for attempt in {1..20}; do
    if [[ -z "$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)" ]]; then
      return 0
    fi
    sleep 0.25
  done
  check_port "${port}"
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempt
  for attempt in {1..30}; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "${label}: ready"
      return 0
    fi
    sleep 1
  done
  echo "${label}: failed to become ready; inspect /tmp/open-compute-*.err" >&2
  return 1
}

show_status() {
  local label
  for label in "${web_label}" "${api_label}" "${agent_label}"; do
    if launchctl print "gui/$(id -u)/${label}" >/dev/null 2>&1; then
      launchctl print "gui/$(id -u)/${label}" |
        awk -v label="${label}" '
          /state =/ && !seen_state { state=$3; seen_state=1 }
          /pid =/ && !seen_pid { pid=$3; seen_pid=1 }
          END { printf "%s: state=%s pid=%s\n", label, state, pid }
        '
    else
      echo "${label}: stopped"
    fi
  done
  lsof -nP -iTCP:3000 -sTCP:LISTEN || true
  lsof -nP -iTCP:8000 -sTCP:LISTEN || true
  lsof -nP -iTCP:8110 -sTCP:LISTEN || true
}

start_all() {
  stop_all
  wait_for_port_free 3000
  wait_for_port_free 8000
  wait_for_port_free 8110

  : > /tmp/open-compute-api.log
  : > /tmp/open-compute-api.err
  : > /tmp/open-compute-agent.log
  : > /tmp/open-compute-agent.err
  : > /tmp/open-compute-web.log
  : > /tmp/open-compute-web.err

  "${uv_bin}" run --directory "${api_dir}" python scripts/upgrade_database.py

  local -a api_command=(
    launchctl submit
    -l "${api_label}"
    -o /tmp/open-compute-api.log
    -e /tmp/open-compute-api.err
    --
    /usr/bin/env
    "PRIVATE_NODE_AGENT_TOKEN=${agent_token}"
    "VLLM_INTERNAL_API_KEY=${vllm_key}"
    "DATABASE_URL=${database_url}"
    "${uv_bin}" run --directory "${api_dir}"
    uvicorn app.main:app
    --reload --reload-dir "${api_dir}/app"
    --host 127.0.0.1 --port 8000
  )
  "${api_command[@]}"

  local -a agent_command=(
    launchctl submit
    -l "${agent_label}"
    -o /tmp/open-compute-agent.log
    -e /tmp/open-compute-agent.err
    --
    /usr/bin/env
    "AGENT_TOKEN=${agent_token}"
    "VLLM_INTERNAL_API_KEY=${vllm_key}"
    "DOCKER_BINARY=${docker_bin:-docker}"
    "${uv_bin}" run --directory "${api_dir}"
    uvicorn --app-dir "${agent_dir}" app.main:app
    --reload --reload-dir "${agent_dir}/app"
    --host 127.0.0.1 --port 8110
  )
  "${agent_command[@]}"

  local -a web_command=(
    launchctl submit
    -l "${web_label}"
    -o /tmp/open-compute-web.log
    -e /tmp/open-compute-web.err
    --
    /usr/bin/env
    "PATH=${node_bin_dir}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    "${corepack_bin}" pnpm --dir "${web_dir}" dev --port 3000
  )
  "${web_command[@]}"

  wait_for_url "API" "http://127.0.0.1:8000/health/live"
  wait_for_url "Agent" "http://127.0.0.1:8110/health/live"
  wait_for_url "Web" "http://127.0.0.1:3000/"
  show_status
}

case "${1:-up}" in
  up)
    start_all
    ;;
  down)
    stop_all
    ;;
  restart)
    start_all
    ;;
  status)
    show_status
    ;;
  *)
    echo "Usage: $0 {up|down|restart|status}" >&2
    exit 2
    ;;
esac
