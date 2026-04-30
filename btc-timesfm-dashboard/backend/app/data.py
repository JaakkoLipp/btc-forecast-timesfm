from __future__ import annotations

import time

import pandas as pd

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
DEFAULT_OHLCV_PAGE_LIMIT = 1000
TIMEFRAME_TO_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}


def create_exchange(exchange_id: str):
    try:
        import ccxt
    except ImportError as exc:
        raise RuntimeError(
            "ccxt is not installed. Install backend dependencies with `uv pip install -e .`."
        ) from exc

    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"Unsupported exchange '{exchange_id}'.")

    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    exchange.load_markets()
    return exchange


def validate_market(exchange, symbol: str, timeframe: str) -> None:
    if not exchange.has.get("fetchOHLCV"):
        raise ValueError(f"Exchange '{exchange.id}' does not support OHLCV fetching.")
    if symbol not in exchange.markets:
        btc_symbols = sorted(market for market in exchange.markets if market.startswith("BTC/"))[:8]
        hint = f" Try one of: {', '.join(btc_symbols)}." if btc_symbols else ""
        raise ValueError(f"Symbol '{symbol}' is not available on {exchange.id}.{hint}")
    timeframes = getattr(exchange, "timeframes", None) or {}
    if timeframes and timeframe not in timeframes:
        supported = ", ".join(sorted(timeframes.keys()))
        raise ValueError(
            f"Timeframe '{timeframe}' is not available on {exchange.id}. Supported: {supported}."
        )


def validate_ohlcv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(OHLCV_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"OHLCV data is missing required columns: {sorted(missing)}")

    validated = frame.copy()
    for column in OHLCV_COLUMNS:
        validated[column] = pd.to_numeric(validated[column], errors="coerce")

    validated = validated.dropna(subset=OHLCV_COLUMNS)
    validated = validated.sort_values("timestamp").drop_duplicates("timestamp")
    validated["timestamp"] = validated["timestamp"].astype("int64")
    validated["datetime"] = pd.to_datetime(validated["timestamp"], unit="ms", utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return validated[
        ["timestamp", "datetime", "open", "high", "low", "close", "volume"]
    ].reset_index(drop=True)


def fetch_ohlcv(exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    if timeframe not in TIMEFRAME_TO_MS:
        raise ValueError(f"Unsupported timeframe '{timeframe}'.")
    if limit <= 0:
        raise ValueError("limit must be positive.")

    exchange = create_exchange(exchange_id)
    validate_market(exchange, symbol, timeframe)
    rows = fetch_ohlcv_rows(exchange, symbol, timeframe, limit)
    if not rows:
        raise RuntimeError(f"No OHLCV candles returned for {exchange_id} {symbol} {timeframe}.")

    frame = pd.DataFrame(rows, columns=OHLCV_COLUMNS)
    return validate_ohlcv_frame(frame)


def fetch_ohlcv_rows(exchange, symbol: str, timeframe: str, limit: int) -> list[list[float]]:
    step_ms = timeframe_to_milliseconds(timeframe)
    page_limit = min(limit, DEFAULT_OHLCV_PAGE_LIMIT)

    if limit <= page_limit:
        latest_rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if len(latest_rows) >= limit:
            return latest_rows[-limit:]

    now_ms = exchange.milliseconds() if hasattr(exchange, "milliseconds") else int(time.time() * 1000)
    since = now_ms - limit * step_ms
    collected: list[list[float]] = []
    seen_timestamps: set[int] = set()

    while len(collected) < limit:
        remaining = limit - len(collected)
        batch_limit = min(page_limit, remaining)
        batch = exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            since=since,
            limit=batch_limit,
        )
        if not batch:
            break

        last_timestamp = int(batch[-1][0])
        added = 0
        for row in batch:
            timestamp = int(row[0])
            if timestamp not in seen_timestamps:
                collected.append(row)
                seen_timestamps.add(timestamp)
                added += 1

        next_since = last_timestamp + step_ms
        if next_since <= since or added == 0:
            break
        since = next_since

    return sorted(collected, key=lambda row: row[0])[-limit:]


def timeframe_to_milliseconds(timeframe: str) -> int:
    try:
        return TIMEFRAME_TO_MS[timeframe]
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe '{timeframe}'.") from exc


def future_time_axis(last_timestamp_ms: int, timeframe: str, horizon: int) -> tuple[list[int], list[str]]:
    step_ms = timeframe_to_milliseconds(timeframe)
    timestamps = [last_timestamp_ms + step_ms * (index + 1) for index in range(horizon)]
    datetimes = [
        pd.to_datetime(ts, unit="ms", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
        for ts in timestamps
    ]
    return timestamps, datetimes


def candles_from_frame(frame: pd.DataFrame) -> list[dict]:
    return validate_ohlcv_frame(frame).to_dict(orient="records")
