# BTC TimesFM Dashboard

Local research dashboard for Bitcoin OHLCV forecasting with Google Research TimesFM 2.5 and walk-forward paper backtesting.

This project is not a trading bot. It does not use exchange API keys, private endpoints, account access, or real order placement.

## Architecture

```text
btc-timesfm-dashboard/
+-- backend/   FastAPI, ccxt, pandas, torch, TimesFM, SQLite, pytest
+-- frontend/  Vite, React, TypeScript, Tailwind CSS, lightweight-charts
+-- scripts/   Linux setup/run helpers
+-- docker-compose.yml
```

## One-command Linux Setup

You can run the Linux script from WSL. From Windows, the project is usually available under `/mnt/d`, for example:

```bash
cd "/mnt/d/Documents/New project 2/btc-timesfm-dashboard"
chmod +x scripts/setup_and_run_linux.sh
./scripts/setup_and_run_linux.sh
```

The frontend and backend ports should be reachable from Windows at `localhost:5173` and `localhost:8000`.

On native Linux, run this from the project root to set up the backend, frontend, current Google Research TimesFM repo, and the real `google/timesfm-2.5-200m-pytorch` checkpoint:

```bash
chmod +x scripts/setup_and_run_linux.sh
./scripts/setup_and_run_linux.sh
```

The script installs `uv` and a local Node.js runtime if needed, creates `backend/.venv`, clones TimesFM into `.vendor/timesfm`, installs it with torch support, warms the model on CPU, runs backend checks, builds the frontend, and starts:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

Useful faster variants:

```bash
./scripts/setup_and_run_linux.sh --skip-model-warmup
./scripts/setup_and_run_linux.sh --skip-tests --skip-frontend-build
./scripts/setup_and_run_linux.sh --fake-forecast
./scripts/setup_and_run_linux.sh --no-start
```

The default is real model mode with `DEV_FAKE_FORECAST=false` and `INFERENCE_DEVICE=cpu`.

## One-command Windows Setup

If you prefer native Windows PowerShell instead of WSL:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_run_windows.ps1
```

Useful faster variants:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_run_windows.ps1 -SkipModelWarmup
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_run_windows.ps1 -SkipTests -SkipFrontendBuild
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_run_windows.ps1 -FakeForecast
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_run_windows.ps1 -NoStart
```

The Windows script follows the same flow as the Linux script and also downloads local Node.js if `node`/`npm` are missing.

## Start / stop after setup

Once `setup_and_run_*` has installed deps and warmed the model, use the lightweight service script for day-to-day starts:

Linux:

```bash
./scripts/service.sh start
./scripts/service.sh status
./scripts/service.sh logs --follow
./scripts/service.sh stop
./scripts/service.sh restart --fake-forecast
```

Windows PowerShell:

```powershell
.\scripts\service.ps1 start
.\scripts\service.ps1 status
.\scripts\service.ps1 logs -Follow
.\scripts\service.ps1 stop
.\scripts\service.ps1 restart -FakeForecast
```

PIDs and rolling logs are kept in `.runtime/` (gitignored). Both scripts respect `BACKEND_PORT`, `FRONTEND_PORT`, `INFERENCE_DEVICE`, `MODEL_CHECKPOINT`, and `DEV_FAKE_FORECAST` overrides via env or flags.

## Screenshots

Placeholder: add dashboard screenshots after running the frontend locally.

## CPU-first MVP

The initial implementation is CPU-only by default:

- `INFERENCE_DEVICE=cpu`
- no CUDA requirement
- no NVIDIA driver requirement
- no GPU Docker image requirement
- TimesFM loads lazily on first forecast request

Forecasting can be slow on CPU, especially the first request because the model may need to download and initialize. Future GPU support can start by setting `INFERENCE_DEVICE=cuda`, but it is not required for this MVP.

## Backend Setup

From `backend/`:

```bash
uv venv
.\.venv\Scripts\activate
uv pip install -e .[dev]
```

Install the current Google Research TimesFM repository:

```bash
git clone https://github.com/google-research/timesfm.git
cd timesfm
uv pip install -e .[torch]
```

Copy the environment file if you want to customize settings:

```bash
copy .env.example .env
```

Run the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Local URLs:

- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

For frontend-only development without loading TimesFM:

```bash
DEV_FAKE_FORECAST=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

From `frontend/`:

```bash
npm install
npm run dev
```

Local URL:

- Frontend: http://localhost:5173

## Tests

From `backend/`:

```bash
uv run --python 3.11 --extra dev pytest
```

The tests do not load the real TimesFM model. They cover signal generation, log-return reconstruction, long/short mock PnL, fee/slippage handling, TP/SL simulation, and backtest metrics.

## Local Evaluation Notes

- OHLCV fetching paginates CCXT requests for larger lookbacks/backtests, since many exchanges cap a single OHLCV response.
- Real TimesFM backtests can be slow on CPU because walk-forward testing runs many forecasts. Use the dashboard's `Walk step`, `Signal index`, and `Max trades` controls to shorten early experiments.
- If an exchange does not support a symbol/timeframe, the backend returns a clear validation error with BTC symbol hints where available.

## Docker Convenience

Docker is optional and intended for local convenience only:

```bash
docker compose up
```

The compose backend defaults to `DEV_FAKE_FORECAST=true` so the UI can be exercised without installing the TimesFM repo inside the container. Use the normal backend setup above for real TimesFM forecasts.

## Disclaimer

This dashboard is for research and paper trading only. It does not provide financial advice and does not execute real trades. Forecasts and mock backtests can be wrong and may not reflect real execution, liquidity, fees, slippage, or market risk.
