import numpy as np
import pandas as pd
import pytest

from app.backtest import calculate_metrics, run_walk_forward_backtest, simulate_trade_exit
from app.forecast import ForecastComputation, close_to_log_returns, reconstruct_prices_from_log_returns
from app.schemas import BacktestRequest, EquityPoint, ForecastResult, TradeSignal


class MockForecaster:
    def forecast(self, close_prices, horizon, target_mode, use_quantiles):
        current = float(close_prices[-1])
        prices = [current * 1.02 for _ in range(horizon)]
        return ForecastComputation(
            result=ForecastResult(
                predicted_prices=prices,
                predicted_target_values=prices,
                last_price=current,
                target_mode=target_mode,
            )
        )


def make_frame(rows=140):
    base = 1_700_000_000_000
    close = 100 + np.arange(rows, dtype=float)
    return pd.DataFrame(
        {
            "timestamp": [base + index * 300_000 for index in range(rows)],
            "open": close - 0.2,
            "high": close + 2.0,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(rows, 10.0),
        }
    )


def test_log_return_transformation_and_price_reconstruction():
    closes = np.array([100.0, 110.0, 121.0])
    returns = close_to_log_returns(closes)
    reconstructed = reconstruct_prices_from_log_returns(121.0, [returns[-1], returns[-1]])

    assert returns[0] == pytest.approx(np.log(1.1))
    assert returns[1] == pytest.approx(np.log(1.1))
    assert reconstructed[-1] == pytest.approx(146.41)


def test_simulate_trade_exit_uses_conservative_same_candle_stop_first():
    future = pd.DataFrame(
        [
            {
                "datetime": "2026-01-01T00:05:00Z",
                "high": 102,
                "low": 98,
                "close": 100,
            }
        ]
    )
    long_signal = TradeSignal(
        signal="long",
        reason="test",
        current_price=100,
        forecast_price=102,
        expected_return_pct=2,
        take_profit_price=101,
        stop_loss_price=99,
        confidence_label="high",
        signal_horizon_index=0,
    )
    short_signal = long_signal.model_copy(
        update={
            "signal": "short",
            "forecast_price": 98,
            "expected_return_pct": -2,
            "take_profit_price": 99,
            "stop_loss_price": 101,
        }
    )

    assert simulate_trade_exit(long_signal, future)[:3] == (99, "2026-01-01T00:05:00Z", "stop_loss")
    assert simulate_trade_exit(short_signal, future)[:3] == (101, "2026-01-01T00:05:00Z", "stop_loss")


def test_walk_forward_backtest_opens_and_closes_mock_trades():
    request = BacktestRequest(
        lookback=20,
        horizon=3,
        backtest_candles=50,
        signal_threshold_pct=0.2,
        take_profit_pct=0.5,
        stop_loss_pct=5,
        fee_pct=0,
        slippage_pct=0,
        walk_forward_step=1,
        max_trades=5,
    )

    response = run_walk_forward_backtest(make_frame(), request, MockForecaster())

    assert response.metrics.total_trades == 5
    assert response.metrics.win_rate_pct == pytest.approx(100)
    assert response.metrics.net_pnl > 0
    assert all(trade.exit_reason == "take_profit" for trade in response.trades)


def test_metrics_calculation_handles_empty_trades():
    metrics = calculate_metrics(
        trades=[],
        equity_curve=[EquityPoint(timestamp=1, datetime="2026-01-01T00:00:00Z", equity=1000)],
        initial_equity=1000,
    )

    assert metrics.total_trades == 0
    assert metrics.win_rate_pct == 0
    assert metrics.final_equity == 1000
