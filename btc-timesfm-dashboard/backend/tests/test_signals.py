import pytest

from app.schemas import ForecastQuantile
from app.signals import generate_trade_signal


def test_generates_long_signal_with_levels():
    signal = generate_trade_signal(
        current_price=100,
        forecast_prices=[100.2, 101.0],
        signal_horizon_index=1,
        signal_threshold_pct=0.5,
        take_profit_pct=1.0,
        stop_loss_pct=0.75,
        allow_short=True,
    )

    assert signal.signal == "long"
    assert signal.expected_return_pct == pytest.approx(1.0)
    assert signal.take_profit_price == pytest.approx(101.0)
    assert signal.stop_loss_price == pytest.approx(99.25)
    assert signal.confidence_label == "medium"


def test_generates_short_signal_when_allowed():
    signal = generate_trade_signal(
        current_price=100,
        forecast_prices=[99.8, 98.5],
        signal_horizon_index=1,
        signal_threshold_pct=0.5,
        take_profit_pct=1.0,
        stop_loss_pct=0.75,
        allow_short=True,
    )

    assert signal.signal == "short"
    assert signal.expected_return_pct == pytest.approx(-1.5)
    assert signal.take_profit_price == pytest.approx(99.0)
    assert signal.stop_loss_price == pytest.approx(100.75)
    assert signal.confidence_label == "high"


def test_generates_hold_inside_threshold_or_when_short_disabled():
    neutral = generate_trade_signal(
        current_price=100,
        forecast_prices=[100.1],
        signal_horizon_index=0,
        signal_threshold_pct=0.5,
        take_profit_pct=1.0,
        stop_loss_pct=0.75,
        allow_short=True,
    )
    short_disabled = generate_trade_signal(
        current_price=100,
        forecast_prices=[98],
        signal_horizon_index=0,
        signal_threshold_pct=0.5,
        take_profit_pct=1.0,
        stop_loss_pct=0.75,
        allow_short=False,
    )

    assert neutral.signal == "hold"
    assert short_disabled.signal == "hold"


def test_quantile_uncertainty_downgrades_confidence():
    signal = generate_trade_signal(
        current_price=100,
        forecast_prices=[104],
        signal_horizon_index=0,
        signal_threshold_pct=0.5,
        take_profit_pct=1.0,
        stop_loss_pct=0.75,
        allow_short=True,
        quantiles=[ForecastQuantile(horizon_index=0, lower=98, median=104, upper=110)],
    )

    assert signal.signal == "long"
    assert signal.confidence_label == "medium"

