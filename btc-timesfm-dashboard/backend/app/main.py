from __future__ import annotations

import math
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.backtest import run_walk_forward_backtest
from app.data import candles_from_frame, fetch_ohlcv, future_time_axis, validate_ohlcv_frame
from app.forecast import ForecastComputation, TimesFMForecaster
from app.mock_trading import estimate_trade_from_signal
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    Candle,
    ForecastRequest,
    ForecastResponse,
    ForecastResult,
    MetadataResponse,
)
from app.settings import Settings, get_settings
from app.signals import generate_trade_signal
from app.storage import cache_candles, init_storage, record_run

settings = get_settings()
forecaster = TimesFMForecaster(settings=settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_storage(settings.SQLITE_PATH)
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DISCLAIMER = (
    "This dashboard is for research and paper trading only. It does not provide financial advice and "
    "does not execute real trades. Forecasts and mock backtests can be wrong and may not reflect real "
    "execution, liquidity, fees, slippage, or market risk."
)


def _validate_request_limits(request: ForecastRequest, settings_: Settings) -> None:
    if request.lookback > settings_.MAX_LOOKBACK:
        raise HTTPException(
            status_code=422,
            detail=f"lookback exceeds MAX_LOOKBACK={settings_.MAX_LOOKBACK}.",
        )
    if request.horizon > settings_.MAX_HORIZON:
        raise HTTPException(status_code=422, detail=f"horizon exceeds MAX_HORIZON={settings_.MAX_HORIZON}.")
    if request.lookback > settings_.MODEL_MAX_CONTEXT:
        raise HTTPException(
            status_code=422,
            detail=f"lookback exceeds compiled MODEL_MAX_CONTEXT={settings_.MODEL_MAX_CONTEXT}.",
        )
    if request.horizon > settings_.MODEL_MAX_HORIZON:
        raise HTTPException(
            status_code=422,
            detail=f"horizon exceeds compiled MODEL_MAX_HORIZON={settings_.MODEL_MAX_HORIZON}.",
        )
    if request.signal_horizon_index is not None and request.signal_horizon_index >= request.horizon:
        raise HTTPException(status_code=422, detail="signal_horizon_index must be less than horizon.")


def _attach_time_axis(forecast: ForecastResult, last_timestamp: int, timeframe: str) -> ForecastResult:
    timestamps, datetimes = future_time_axis(last_timestamp, timeframe, len(forecast.predicted_prices))
    if forecast.quantiles:
        for quantile, timestamp, datetime_value in zip(
            forecast.quantiles,
            timestamps,
            datetimes,
            strict=False,
        ):
            quantile.timestamp = timestamp
            quantile.datetime = datetime_value
    return forecast.model_copy(update={"timestamps": timestamps, "datetimes": datetimes})


def _forecast_from_frame(
    frame: pd.DataFrame,
    request: ForecastRequest,
) -> tuple[ForecastComputation, ForecastResult]:
    computation = forecaster.forecast(
        close_prices=frame["close"].to_numpy(),
        horizon=request.horizon,
        target_mode=request.target_mode,
        use_quantiles=request.use_quantiles,
    )
    forecast = _attach_time_axis(
        computation.result,
        last_timestamp=int(frame.iloc[-1]["timestamp"]),
        timeframe=request.timeframe,
    )
    return computation, forecast


def _ensure_candle_count(frame: pd.DataFrame, requested: int, purpose: str) -> None:
    if len(frame) < requested:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Exchange returned {len(frame)} candles for {purpose}, but {requested} are required. "
                "Try a shorter lookback/backtest range or a different exchange/timeframe."
            ),
        )


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "model_loaded": forecaster.model_loaded,
        "inference_device": settings.INFERENCE_DEVICE,
    }


@app.get("/metadata", response_model=MetadataResponse)
def metadata() -> MetadataResponse:
    return MetadataResponse(
        supported_exchanges=["binance", "coinbase", "kraken"],
        supported_symbols=["BTC/USDT", "BTC/USD", "BTC/EUR"],
        supported_timeframes=["1m", "5m", "15m", "1h", "4h", "1d"],
        defaults={
            "exchange": settings.DEFAULT_EXCHANGE,
            "symbol": settings.DEFAULT_SYMBOL,
            "timeframe": settings.DEFAULT_TIMEFRAME,
            "lookback": settings.DEFAULT_LOOKBACK,
            "horizon": settings.DEFAULT_HORIZON,
            "target_mode": "log_return",
            "signal_threshold_pct": 0.5,
            "take_profit_pct": 1.0,
            "stop_loss_pct": 0.75,
            "position_size": 1000.0,
            "fee_pct": 0.1,
            "slippage_pct": 0.05,
            "allow_short": True,
        },
        model={
            "checkpoint": settings.MODEL_CHECKPOINT,
            "max_context": settings.MODEL_MAX_CONTEXT,
            "max_horizon": settings.MODEL_MAX_HORIZON,
            "use_quantiles": settings.USE_QUANTILES,
            "inference_device": settings.INFERENCE_DEVICE,
            "cpu_first": True,
        },
        disclaimer=DISCLAIMER,
    )


@app.post("/forecast", response_model=ForecastResponse)
def run_forecast(request: ForecastRequest) -> ForecastResponse:
    _validate_request_limits(request, settings)
    try:
        frame = fetch_ohlcv(request.exchange, request.symbol, request.timeframe, request.lookback)
        frame = validate_ohlcv_frame(frame)
        _ensure_candle_count(frame, request.lookback, "forecast")
        candles = [Candle(**row) for row in candles_from_frame(frame)]
        cache_candles(settings.SQLITE_PATH, request.exchange, request.symbol, request.timeframe, candles)

        computation, forecast = _forecast_from_frame(frame, request)
        signal = generate_trade_signal(
            current_price=float(frame.iloc[-1]["close"]),
            forecast_prices=forecast.predicted_prices,
            signal_horizon_index=request.signal_horizon_index,
            signal_threshold_pct=request.signal_threshold_pct,
            take_profit_pct=request.take_profit_pct,
            stop_loss_pct=request.stop_loss_pct,
            allow_short=request.allow_short,
            quantiles=forecast.quantiles,
        )
        estimate = estimate_trade_from_signal(
            signal=signal,
            position_size=request.position_size,
            fee_pct=request.fee_pct,
            slippage_pct=request.slippage_pct,
        )

        response = ForecastResponse(
            request=request,
            candles=candles,
            forecast=forecast,
            signal=signal,
            mock_estimate=estimate,
            warnings=computation.warnings,
        )
        record_run(settings.SQLITE_PATH, "forecast_runs", request.model_dump(), response.model_dump())
        return response
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/backtest", response_model=BacktestResponse)
def run_backtest(request: BacktestRequest) -> BacktestResponse:
    _validate_request_limits(request, settings)
    requested_limit = request.lookback + request.backtest_candles + request.horizon + 5
    limit = min(settings.MAX_LOOKBACK + request.horizon, requested_limit)
    try:
        frame = fetch_ohlcv(request.exchange, request.symbol, request.timeframe, limit)
        _ensure_candle_count(frame, limit, "backtest")
        cache_candles(
            settings.SQLITE_PATH,
            request.exchange,
            request.symbol,
            request.timeframe,
            [Candle(**row) for row in candles_from_frame(frame)],
        )
        response = run_walk_forward_backtest(frame, request, forecaster)
        record_run(settings.SQLITE_PATH, "backtest_runs", request.model_dump(), response.model_dump())
        return response
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/sample", response_model=ForecastResponse)
def sample() -> ForecastResponse:
    horizon = settings.DEFAULT_HORIZON
    lookback = 240
    base_ts = 1_700_000_000_000
    step = 300_000
    prices = 42_000 + np.cumsum(np.sin(np.linspace(0, 14, lookback)) * 28 + 3)
    rows = []
    for index, close in enumerate(prices):
        open_price = prices[index - 1] if index else close
        spread = max(20, abs(close - open_price) * 1.5)
        rows.append(
            {
                "timestamp": base_ts + index * step,
                "open": float(open_price),
                "high": float(max(open_price, close) + spread),
                "low": float(min(open_price, close) - spread),
                "close": float(close),
                "volume": float(20 + 5 * math.sin(index / 7)),
            }
        )
    frame = validate_ohlcv_frame(pd.DataFrame(rows))
    request = ForecastRequest(lookback=lookback, horizon=horizon)

    temp_settings = settings.model_copy(update={"DEV_FAKE_FORECAST": True})
    sample_forecaster = TimesFMForecaster(settings=temp_settings)
    computation = sample_forecaster.forecast(frame["close"].to_numpy(), horizon, "log_return", True)
    forecast = _attach_time_axis(computation.result, int(frame.iloc[-1]["timestamp"]), request.timeframe)
    signal = generate_trade_signal(
        current_price=float(frame.iloc[-1]["close"]),
        forecast_prices=forecast.predicted_prices,
        signal_horizon_index=None,
        signal_threshold_pct=request.signal_threshold_pct,
        take_profit_pct=request.take_profit_pct,
        stop_loss_pct=request.stop_loss_pct,
        allow_short=request.allow_short,
        quantiles=forecast.quantiles,
    )
    estimate = estimate_trade_from_signal(
        signal,
        request.position_size,
        request.fee_pct,
        request.slippage_pct,
    )
    return ForecastResponse(
        request=request,
        candles=[Candle(**row) for row in candles_from_frame(frame)],
        forecast=forecast,
        signal=signal,
        mock_estimate=estimate,
        warnings=["Sample endpoint uses generated data for frontend development."],
    )
