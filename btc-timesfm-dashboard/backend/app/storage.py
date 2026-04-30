from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from app.schemas import Candle


def connect(sqlite_path: str) -> sqlite3.Connection:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_storage(sqlite_path: str) -> None:
    with connect(sqlite_path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                datetime TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (exchange, symbol, timeframe, timestamp)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL
            )
            """
        )


def cache_candles(
    sqlite_path: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    candles: Iterable[Candle | dict],
) -> None:
    rows = []
    for candle in candles:
        payload = candle.model_dump() if isinstance(candle, Candle) else candle
        rows.append(
            (
                exchange,
                symbol,
                timeframe,
                payload["timestamp"],
                payload["datetime"],
                payload["open"],
                payload["high"],
                payload["low"],
                payload["close"],
                payload["volume"],
            )
        )

    with connect(sqlite_path) as db:
        db.executemany(
            """
            INSERT OR REPLACE INTO candles (
                exchange, symbol, timeframe, timestamp, datetime, open, high, low, close, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def record_run(sqlite_path: str, table: str, request: dict, response: dict) -> None:
    if table not in {"forecast_runs", "backtest_runs"}:
        raise ValueError("Unsupported run table.")
    with connect(sqlite_path) as db:
        db.execute(
            f"INSERT INTO {table} (request_json, response_json) VALUES (?, ?)",
            (json.dumps(request), json.dumps(response)),
        )

