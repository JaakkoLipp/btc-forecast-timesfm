# BTC TimesFM Dashboard Backend

FastAPI backend for local BTC OHLCV fetching, TimesFM 2.5 forecasting, mock signal generation, and walk-forward paper backtesting.

## Setup

```bash
uv venv
.\.venv\Scripts\activate
uv pip install -e .[dev]
```

Install TimesFM from the current Google Research repository:

```bash
git clone https://github.com/google-research/timesfm.git
cd timesfm
uv pip install -e .[torch]
```

Run locally:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The MVP is CPU-first. `INFERENCE_DEVICE=cpu` is the default, the backend does not require CUDA or NVIDIA drivers, and the first real forecast may be slow while the model downloads and loads.

For frontend work without loading TimesFM, set `DEV_FAKE_FORECAST=true`.

