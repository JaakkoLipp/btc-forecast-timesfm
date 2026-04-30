import pytest

from app.mock_trading import calculate_trade_pnl, close_trade, estimate_trade_from_signal
from app.schemas import TradeSignal


def test_long_pnl_includes_fees_and_slippage():
    pnl = calculate_trade_pnl(
        side="long",
        entry_price=100,
        exit_price=110,
        position_size=1000,
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    assert pnl["quantity"] == pytest.approx(10)
    assert pnl["gross_pnl"] == pytest.approx(100)
    assert pnl["fees_paid"] == pytest.approx(2.1)
    assert pnl["slippage_cost"] == pytest.approx(1.05)
    assert pnl["net_pnl"] == pytest.approx(96.85)


def test_short_pnl_includes_fees_and_slippage():
    pnl = calculate_trade_pnl(
        side="short",
        entry_price=100,
        exit_price=90,
        position_size=1000,
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    assert pnl["quantity"] == pytest.approx(10)
    assert pnl["gross_pnl"] == pytest.approx(100)
    assert pnl["fees_paid"] == pytest.approx(1.9)
    assert pnl["slippage_cost"] == pytest.approx(0.95)
    assert pnl["net_pnl"] == pytest.approx(97.15)


def test_estimate_trade_from_hold_signal_has_zero_pnl():
    estimate = estimate_trade_from_signal(
        TradeSignal(
            signal="hold",
            reason="test",
            current_price=100,
            forecast_price=100,
            expected_return_pct=0,
            confidence_label="low",
            signal_horizon_index=0,
        ),
        position_size=1000,
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    assert estimate.side == "hold"
    assert estimate.estimated_net_pnl == 0


def test_close_trade_returns_mock_trade_record():
    trade = close_trade(
        side="long",
        entry_time="2026-01-01T00:00:00Z",
        exit_time="2026-01-01T00:05:00Z",
        entry_price=100,
        exit_price=101,
        position_size=1000,
        fee_pct=0,
        slippage_pct=0,
        exit_reason="take_profit",
        holding_candles=1,
        trade_id="test-trade",
    )

    assert trade.id == "test-trade"
    assert trade.net_pnl == pytest.approx(10)
    assert trade.return_pct == pytest.approx(1)

