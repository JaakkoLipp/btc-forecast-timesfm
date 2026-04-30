import pytest

from app.data import fetch_ohlcv_rows, validate_market


class FakeExchange:
    id = "fake"
    has = {"fetchOHLCV": True}
    markets = {"BTC/USDT": object(), "BTC/USD": object()}
    timeframes = {"5m": "5m"}

    def __init__(self, rows, page_cap=None):
        self.rows = rows
        self.page_cap = page_cap
        self.calls = []

    def milliseconds(self):
        return self.rows[-1][0] + 300_000

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        if self.page_cap is not None:
            limit = min(limit, self.page_cap)
        self.calls.append({"symbol": symbol, "timeframe": timeframe, "since": since, "limit": limit})
        if since is None:
            return self.rows[-limit:]
        eligible = [row for row in self.rows if row[0] >= since]
        return eligible[:limit]


def make_rows(count):
    base = 1_700_000_000_000
    return [
        [base + index * 300_000, 100 + index, 101 + index, 99 + index, 100.5 + index, 10]
        for index in range(count)
    ]


def test_fetch_ohlcv_rows_paginates_large_requests():
    exchange = FakeExchange(make_rows(1505))

    rows = fetch_ohlcv_rows(exchange, "BTC/USDT", "5m", 1200)

    assert len(rows) == 1200
    assert rows == exchange.rows[-1200:]
    assert len(exchange.calls) > 1
    assert exchange.calls[0]["since"] is not None


def test_fetch_ohlcv_rows_uses_single_call_for_small_requests():
    exchange = FakeExchange(make_rows(200))

    rows = fetch_ohlcv_rows(exchange, "BTC/USDT", "5m", 50)

    assert len(rows) == 50
    assert rows == exchange.rows[-50:]
    assert len(exchange.calls) == 1
    assert exchange.calls[0]["since"] is None


def test_fetch_ohlcv_rows_continues_when_exchange_caps_page_size():
    exchange = FakeExchange(make_rows(900), page_cap=300)

    rows = fetch_ohlcv_rows(exchange, "BTC/USDT", "5m", 750)

    assert len(rows) == 750
    assert rows == exchange.rows[-750:]
    assert len(exchange.calls) == 4


def test_validate_market_reports_symbol_hint():
    exchange = FakeExchange(make_rows(5))

    with pytest.raises(ValueError, match="Try one of"):
        validate_market(exchange, "ETH/USDT", "5m")
