#!/usr/bin/env bash
# service.sh - start/stop/status/logs helper for the BTC TimesFM dashboard.
#
# Assumes ./scripts/setup_and_run_linux.sh has already created the backend
# venv and installed frontend deps. PIDs and logs live in <project>/.runtime/.
#
# Usage:
#   ./scripts/service.sh start [--fake-forecast]
#   ./scripts/service.sh stop
#   ./scripts/service.sh restart [--fake-forecast]
#   ./scripts/service.sh status
#   ./scripts/service.sh logs [--follow]

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
RUNTIME_DIR="${PROJECT_ROOT}/.runtime"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
INFERENCE_DEVICE="${INFERENCE_DEVICE:-cpu}"
MODEL_CHECKPOINT="${MODEL_CHECKPOINT:-google/timesfm-2.5-200m-pytorch}"
DEV_FAKE_FORECAST="${DEV_FAKE_FORECAST:-false}"

BACKEND_PID_FILE="${RUNTIME_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/frontend.pid"
BACKEND_LOG="${RUNTIME_DIR}/backend.log"
FRONTEND_LOG="${RUNTIME_DIR}/frontend.log"

# If a Node.js was vendored by setup_and_run_linux.sh, prefer it.
NODE_BIN="$(find "${PROJECT_ROOT}/.vendor" -maxdepth 2 -type d -name "node-v*-linux-*" 2>/dev/null | sort | tail -n 1)"
if [[ -n "${NODE_BIN}" && -x "${NODE_BIN}/bin/node" ]]; then
  export PATH="${NODE_BIN}/bin:${PATH}"
fi

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

read_pid() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    tr -d '[:space:]' <"${file}" 2>/dev/null
  fi
}

is_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

stop_tree() {
  local pid="$1"
  [[ -n "${pid}" ]] || return 0
  is_alive "${pid}" || return 0

  # Best effort: kill the whole process group, then orphan children, then the
  # tracked pid itself. Some children (vite spawning esbuild) are reparented
  # quickly, so we do all three.
  kill -- -"${pid}" 2>/dev/null || true
  pkill -P "${pid}" 2>/dev/null || true
  kill "${pid}" 2>/dev/null || true

  for _ in 1 2 3 4 5; do
    is_alive "${pid}" || return 0
    sleep 0.2
  done
  kill -9 -- -"${pid}" 2>/dev/null || true
  kill -9 "${pid}" 2>/dev/null || true
}

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt "sport = :${port}" 2>/dev/null | grep -q LISTEN
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP -sTCP:LISTEN -nP 2>/dev/null | awk '{print $9}' | grep -q ":${port}\$"
  else
    (echo > "/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1
  fi
}

wait_for_port() {
  local port="$1"
  local label="$2"
  local attempts="${3:-60}"
  for _ in $(seq 1 "${attempts}"); do
    if port_listening "${port}"; then
      echo "${label} is ready on port ${port}"
      return 0
    fi
    sleep 1
  done
  echo "${label} did not become ready on port ${port} (check logs)" >&2
  return 1
}

status_line() {
  local label="$1"
  local pid="$2"
  local port="$3"
  local alive=0
  local listening=0
  is_alive "${pid}" && alive=1
  port_listening "${port}" && listening=1

  if [[ "${alive}" -eq 1 && "${listening}" -eq 1 ]]; then
    printf "  %-9s running (pid %s, port %s)\n" "${label}" "${pid}" "${port}"
  elif [[ "${alive}" -eq 1 ]]; then
    printf "  %-9s process up, not yet listening (pid %s, port %s)\n" "${label}" "${pid}" "${port}"
  elif [[ "${listening}" -eq 1 ]]; then
    printf "  %-9s port %s in use but no PID file (started elsewhere?)\n" "${label}" "${port}"
  else
    printf "  %-9s stopped\n" "${label}"
  fi
}

action_status() {
  local backend_pid frontend_pid
  backend_pid="$(read_pid "${BACKEND_PID_FILE}")"
  frontend_pid="$(read_pid "${FRONTEND_PID_FILE}")"
  echo "BTC TimesFM Dashboard:"
  status_line "Backend"  "${backend_pid}"  "${BACKEND_PORT}"
  status_line "Frontend" "${frontend_pid}" "${FRONTEND_PORT}"
}

action_start() {
  local backend_python="${BACKEND_DIR}/.venv/bin/python"
  if [[ ! -x "${backend_python}" ]]; then
    echo "Backend venv not found at ${backend_python}." >&2
    echo "Run ./scripts/setup_and_run_linux.sh --no-start first." >&2
    exit 1
  fi
  if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
    echo "Frontend deps missing in ${FRONTEND_DIR}/node_modules." >&2
    echo "Run ./scripts/setup_and_run_linux.sh --no-start first." >&2
    exit 1
  fi
  if ! command -v setsid >/dev/null 2>&1; then
    echo "setsid not found (install util-linux)." >&2
    exit 1
  fi

  mkdir -p "${RUNTIME_DIR}"

  local existing
  existing="$(read_pid "${BACKEND_PID_FILE}")"
  if is_alive "${existing}"; then
    echo "Backend already running (pid ${existing}). Use 'restart' to bounce it."
  else
    echo "Starting backend..."
    (
      cd "${BACKEND_DIR}"
      APP_NAME="BTC TimesFM Dashboard" \
      CORS_ORIGINS="http://localhost:${FRONTEND_PORT}" \
      DEV_FAKE_FORECAST="${DEV_FAKE_FORECAST}" \
      INFERENCE_DEVICE="${INFERENCE_DEVICE}" \
      MODEL_CHECKPOINT="${MODEL_CHECKPOINT}" \
      SQLITE_PATH="${BACKEND_DIR}/btc_timesfm.db" \
      setsid "${backend_python}" -m uvicorn app.main:app \
        --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" \
        >"${BACKEND_LOG}" 2>&1 </dev/null &
      echo $! >"${BACKEND_PID_FILE}"
    )
    wait_for_port "${BACKEND_PORT}" "Backend" || true
  fi

  existing="$(read_pid "${FRONTEND_PID_FILE}")"
  if is_alive "${existing}"; then
    echo "Frontend already running (pid ${existing})."
  else
    echo "Starting frontend..."
    (
      cd "${FRONTEND_DIR}"
      VITE_API_BASE_URL="http://localhost:${BACKEND_PORT}" \
      setsid npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" \
        >"${FRONTEND_LOG}" 2>&1 </dev/null &
      echo $! >"${FRONTEND_PID_FILE}"
    )
    wait_for_port "${FRONTEND_PORT}" "Frontend" || true
  fi

  echo ""
  action_status
  cat <<EOF

  http://localhost:${FRONTEND_PORT}  (frontend)
  http://localhost:${BACKEND_PORT}   (backend)
  http://localhost:${BACKEND_PORT}/docs   (API docs)

  DEV_FAKE_FORECAST=${DEV_FAKE_FORECAST}  INFERENCE_DEVICE=${INFERENCE_DEVICE}

  Logs: ./scripts/service.sh logs --follow
  Stop: ./scripts/service.sh stop
EOF
}

action_stop() {
  local backend_pid frontend_pid
  frontend_pid="$(read_pid "${FRONTEND_PID_FILE}")"
  backend_pid="$(read_pid "${BACKEND_PID_FILE}")"

  if [[ -n "${frontend_pid}" ]]; then
    echo "Stopping frontend (pid ${frontend_pid})..."
    stop_tree "${frontend_pid}"
  else
    echo "Frontend not tracked."
  fi
  rm -f "${FRONTEND_PID_FILE}"

  if [[ -n "${backend_pid}" ]]; then
    echo "Stopping backend (pid ${backend_pid})..."
    stop_tree "${backend_pid}"
  else
    echo "Backend not tracked."
  fi
  rm -f "${BACKEND_PID_FILE}"

  echo ""
  action_status
}

action_restart() {
  action_stop
  sleep 1
  action_start
}

action_logs() {
  local follow=0
  for arg in "$@"; do
    case "${arg}" in
      --follow|-f) follow=1 ;;
    esac
  done

  if [[ ! -f "${BACKEND_LOG}" && ! -f "${FRONTEND_LOG}" ]]; then
    echo "No logs found in ${RUNTIME_DIR}. Has the service been started?" >&2
    exit 1
  fi

  if [[ "${follow}" -eq 1 ]]; then
    [[ -f "${BACKEND_LOG}" ]] && { echo "--- backend.log (last 20) ---"; tail -n 20 "${BACKEND_LOG}"; }
    [[ -f "${FRONTEND_LOG}" ]] && { echo ""; echo "--- frontend.log (last 20) ---"; tail -n 20 "${FRONTEND_LOG}"; }
    echo ""
    echo "Following both logs (Ctrl+C to exit)."
    if [[ -f "${BACKEND_LOG}" && -f "${FRONTEND_LOG}" ]]; then
      tail -f "${BACKEND_LOG}" "${FRONTEND_LOG}"
    elif [[ -f "${BACKEND_LOG}" ]]; then
      tail -f "${BACKEND_LOG}"
    else
      tail -f "${FRONTEND_LOG}"
    fi
  else
    [[ -f "${BACKEND_LOG}" ]] && { echo "--- backend.log (last 50) ---"; tail -n 50 "${BACKEND_LOG}"; }
    [[ -f "${FRONTEND_LOG}" ]] && { echo ""; echo "--- frontend.log (last 50) ---"; tail -n 50 "${FRONTEND_LOG}"; }
  fi
}

main() {
  if [[ $# -eq 0 ]]; then
    usage
    exit 1
  fi

  local action="$1"
  shift

  for arg in "$@"; do
    case "${arg}" in
      --fake-forecast) DEV_FAKE_FORECAST=true ;;
    esac
  done

  case "${action}" in
    start)   action_start ;;
    stop)    action_stop ;;
    restart) action_restart ;;
    status)  action_status ;;
    logs)    action_logs "$@" ;;
    -h|--help) usage ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
