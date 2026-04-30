#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
TIMESFM_DIR="${TIMESFM_DIR:-${PROJECT_ROOT}/.vendor/timesfm}"
NODE_VERSION="${NODE_VERSION:-20.18.1}"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
INFERENCE_DEVICE="${INFERENCE_DEVICE:-cpu}"
MODEL_CHECKPOINT="${MODEL_CHECKPOINT:-google/timesfm-2.5-200m-pytorch}"

RUN_TESTS="${RUN_TESTS:-1}"
RUN_FRONTEND_BUILD="${RUN_FRONTEND_BUILD:-1}"
WARM_MODEL="${WARM_MODEL:-1}"
START_SERVERS="${START_SERVERS:-1}"
DEV_FAKE_FORECAST="${DEV_FAKE_FORECAST:-false}"

BACKEND_PID=""
FRONTEND_PID=""

usage() {
  cat <<'EOF'
Usage: ./scripts/setup_and_run_linux.sh [options]

Sets up and runs the local BTC TimesFM dashboard on Linux.

Default behavior:
  - installs uv if missing
  - creates backend/.venv with Python 3.11
  - installs backend dependencies
  - clones/updates google-research/timesfm into .vendor/timesfm
  - installs TimesFM editable with torch support
  - downloads/warms google/timesfm-2.5-200m-pytorch on CPU
  - installs frontend dependencies
  - runs backend tests and frontend build
  - starts backend and frontend dev servers

Options:
  --skip-tests             Skip pytest/ruff checks
  --skip-frontend-build    Skip npm production build
  --skip-model-warmup      Install TimesFM but do not pre-download/warm the checkpoint
  --no-start               Set up and verify, but do not start servers
  --fake-forecast          Start backend with DEV_FAKE_FORECAST=true
  -h, --help               Show this help

Useful environment variables:
  INFERENCE_DEVICE=cpu|cuda        Default: cpu
  MODEL_CHECKPOINT=...             Default: google/timesfm-2.5-200m-pytorch
  NODE_VERSION=20.18.1
  BACKEND_PORT=8000
  FRONTEND_PORT=5173
  TIMESFM_DIR=/path/to/timesfm
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tests)
      RUN_TESTS=0
      shift
      ;;
    --skip-frontend-build)
      RUN_FRONTEND_BUILD=0
      shift
      ;;
    --skip-model-warmup)
      WARM_MODEL=0
      shift
      ;;
    --no-start)
      START_SERVERS=0
      shift
      ;;
    --fake-forecast)
      DEV_FAKE_FORECAST=true
      WARM_MODEL=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

log() {
  printf '\n==> %s\n' "$*"
}

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    return 1
  fi
}

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  need_command uv
}

ensure_node() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return
  fi

  local machine
  local node_arch
  machine="$(uname -m)"
  case "${machine}" in
    x86_64|amd64)
      node_arch="x64"
      ;;
    aarch64|arm64)
      node_arch="arm64"
      ;;
    *)
      echo "Unsupported Linux architecture for bundled Node.js: ${machine}" >&2
      exit 2
      ;;
  esac

  local node_name="node-v${NODE_VERSION}-linux-${node_arch}"
  local node_dir="${PROJECT_ROOT}/.vendor/${node_name}"
  local archive="${PROJECT_ROOT}/.vendor/${node_name}.tar.xz"

  if [[ ! -x "${node_dir}/bin/npm" ]]; then
    log "Installing local Node.js ${NODE_VERSION}"
    mkdir -p "${PROJECT_ROOT}/.vendor"
    curl -fL "https://nodejs.org/dist/v${NODE_VERSION}/${node_name}.tar.xz" -o "${archive}"
    rm -rf "${node_dir}"
    tar -xJf "${archive}" -C "${PROJECT_ROOT}/.vendor"
  fi

  export PATH="${node_dir}/bin:${PATH}"
  need_command node
  need_command npm
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"
  for _ in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "${label} is ready: ${url}"
      return 0
    fi
    sleep 1
  done
  echo "${label} did not become ready: ${url}" >&2
  return 1
}

install_timesfm() {
  if [[ ! -d "${TIMESFM_DIR}/.git" ]]; then
    log "Cloning Google Research TimesFM"
    mkdir -p "$(dirname "${TIMESFM_DIR}")"
    git clone https://github.com/google-research/timesfm.git "${TIMESFM_DIR}"
  else
    log "Updating Google Research TimesFM"
    git -C "${TIMESFM_DIR}" pull --ff-only
  fi

  log "Installing TimesFM with torch support"
  uv pip install --python "${BACKEND_DIR}/.venv/bin/python" -e "${TIMESFM_DIR}[torch]"
}

warm_timesfm_model() {
  if [[ "${WARM_MODEL}" != "1" ]]; then
    return
  fi

  log "Downloading and warming TimesFM checkpoint on ${INFERENCE_DEVICE}"
  INFERENCE_DEVICE="${INFERENCE_DEVICE}" \
  MODEL_CHECKPOINT="${MODEL_CHECKPOINT}" \
  "${BACKEND_DIR}/.venv/bin/python" - <<'PY'
import os

import numpy as np
import torch
import timesfm

device = os.environ.get("INFERENCE_DEVICE", "cpu")
checkpoint = os.environ.get("MODEL_CHECKPOINT", "google/timesfm-2.5-200m-pytorch")

if device == "cuda" and not torch.cuda.is_available():
    raise SystemExit(
        "INFERENCE_DEVICE=cuda was requested, but CUDA is unavailable. "
        "Use INFERENCE_DEVICE=cpu for CPU-only evaluation."
    )

torch.set_float32_matmul_precision("high")
model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint)
model.compile(
    timesfm.ForecastConfig(
        max_context=128,
        max_horizon=8,
        normalize_inputs=True,
        use_continuous_quantile_head=True,
        force_flip_invariance=True,
        infer_is_positive=True,
        fix_quantile_crossing=True,
    )
)
point_forecast, quantile_forecast = model.forecast(
    horizon=1,
    inputs=[np.linspace(0, 1, 64)],
)
print(f"TimesFM warmup complete: point={float(point_forecast[0][0]):.6f}")
print(f"Quantiles available: {quantile_forecast is not None}")
PY
}

write_backend_env() {
  if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
    log "Creating backend/.env"
    cp "${BACKEND_DIR}/.env.example" "${BACKEND_DIR}/.env"
  fi
}

install_backend() {
  log "Creating Python 3.11 backend environment"
  uv venv --python 3.11 "${BACKEND_DIR}/.venv"

  log "Installing backend dependencies"
  uv pip install --python "${BACKEND_DIR}/.venv/bin/python" -e "${BACKEND_DIR}[dev]"
}

install_frontend() {
  log "Installing frontend dependencies"
  (cd "${FRONTEND_DIR}" && npm install)
}

run_checks() {
  if [[ "${RUN_TESTS}" == "1" ]]; then
    log "Running backend ruff and pytest"
    (cd "${BACKEND_DIR}" && ./.venv/bin/python -m ruff check .)
    (cd "${BACKEND_DIR}" && ./.venv/bin/python -m pytest)
  fi

  if [[ "${RUN_FRONTEND_BUILD}" == "1" ]]; then
    log "Building frontend"
    (cd "${FRONTEND_DIR}" && npm run build)
  fi
}

start_servers() {
  if [[ "${START_SERVERS}" != "1" ]]; then
    log "Setup complete. Server start skipped."
    return
  fi

  log "Starting backend"
  (
    cd "${BACKEND_DIR}"
    APP_NAME="BTC TimesFM Dashboard" \
    CORS_ORIGINS="http://localhost:${FRONTEND_PORT}" \
    DEV_FAKE_FORECAST="${DEV_FAKE_FORECAST}" \
    INFERENCE_DEVICE="${INFERENCE_DEVICE}" \
    MODEL_CHECKPOINT="${MODEL_CHECKPOINT}" \
    SQLITE_PATH="${BACKEND_DIR}/btc_timesfm.db" \
    ./.venv/bin/python -m uvicorn app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
  ) &
  BACKEND_PID=$!

  wait_for_http "http://localhost:${BACKEND_PORT}/health" "Backend"

  log "Starting frontend"
  (
    cd "${FRONTEND_DIR}"
    VITE_API_BASE_URL="http://localhost:${BACKEND_PORT}" \
    npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
  ) &
  FRONTEND_PID=$!

  wait_for_http "http://localhost:${FRONTEND_PORT}" "Frontend"

  cat <<EOF

Dashboard is running.
  Frontend: http://localhost:${FRONTEND_PORT}
  Backend:  http://localhost:${BACKEND_PORT}
  API docs: http://localhost:${BACKEND_PORT}/docs

DEV_FAKE_FORECAST=${DEV_FAKE_FORECAST}
INFERENCE_DEVICE=${INFERENCE_DEVICE}
MODEL_CHECKPOINT=${MODEL_CHECKPOINT}

Press Ctrl+C to stop both servers.
EOF

  wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
}

main() {
  if [[ "${INFERENCE_DEVICE}" != "cpu" && "${INFERENCE_DEVICE}" != "cuda" ]]; then
    echo "INFERENCE_DEVICE must be 'cpu' or 'cuda'." >&2
    exit 2
  fi

  need_command bash
  need_command curl
  need_command git
  need_command tar
  ensure_uv
  ensure_node

  write_backend_env
  install_backend

  if [[ "${DEV_FAKE_FORECAST}" != "true" ]]; then
    install_timesfm
    warm_timesfm_model
  else
    log "Skipping TimesFM install/warmup because DEV_FAKE_FORECAST=true"
  fi

  install_frontend
  run_checks
  start_servers
}

main "$@"
