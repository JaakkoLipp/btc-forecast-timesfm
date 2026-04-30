from __future__ import annotations

from app.schemas import ForecastQuantile, TradeSignal


def _confidence_from_ratio(abs_expected_return_pct: float, signal_threshold_pct: float) -> str:
    threshold = max(signal_threshold_pct, 1e-9)
    ratio = abs_expected_return_pct / threshold
    if ratio < 1.5:
        return "low"
    if ratio < 3:
        return "medium"
    return "high"


def _downgrade_confidence(label: str) -> str:
    if label == "high":
        return "medium"
    if label == "medium":
        return "low"
    return "low"


def _quantile_at(quantiles: list[ForecastQuantile] | None, horizon_index: int) -> ForecastQuantile | None:
    if not quantiles:
        return None
    for quantile in quantiles:
        if quantile.horizon_index == horizon_index:
            return quantile
    return None


def generate_trade_signal(
    current_price: float,
    forecast_prices: list[float],
    signal_horizon_index: int | None,
    signal_threshold_pct: float,
    take_profit_pct: float,
    stop_loss_pct: float,
    allow_short: bool,
    quantiles: list[ForecastQuantile] | None = None,
) -> TradeSignal:
    if current_price <= 0:
        raise ValueError("current_price must be positive.")
    if not forecast_prices:
        raise ValueError("forecast_prices cannot be empty.")

    selected_index = len(forecast_prices) - 1 if signal_horizon_index is None else signal_horizon_index
    if selected_index < 0 or selected_index >= len(forecast_prices):
        raise ValueError(
            f"signal_horizon_index={selected_index} is outside forecast range 0..{len(forecast_prices) - 1}."
        )

    forecast_price = float(forecast_prices[selected_index])
    expected_return_pct = ((forecast_price - current_price) / current_price) * 100
    confidence = _confidence_from_ratio(abs(expected_return_pct), signal_threshold_pct)

    if expected_return_pct >= signal_threshold_pct:
        side = "long"
        take_profit_price = current_price * (1 + take_profit_pct / 100)
        stop_loss_price = current_price * (1 - stop_loss_pct / 100)
        reason = f"Forecast return {expected_return_pct:.2f}% is above threshold {signal_threshold_pct:.2f}%."
    elif allow_short and expected_return_pct <= -signal_threshold_pct:
        side = "short"
        take_profit_price = current_price * (1 - take_profit_pct / 100)
        stop_loss_price = current_price * (1 + stop_loss_pct / 100)
        reason = (
            f"Forecast return {expected_return_pct:.2f}% "
            f"is below threshold -{signal_threshold_pct:.2f}%."
        )
    else:
        side = "hold"
        take_profit_price = None
        stop_loss_price = None
        confidence = "low"
        reason = f"Forecast return {expected_return_pct:.2f}% is inside the threshold band."

    selected_quantile = _quantile_at(quantiles, selected_index)
    if selected_quantile and side != "hold":
        band_width_pct = ((selected_quantile.upper - selected_quantile.lower) / current_price) * 100
        directional_disagrees = (
            side == "long" and selected_quantile.lower <= current_price
        ) or (
            side == "short" and selected_quantile.upper >= current_price
        )
        too_wide = band_width_pct > max(abs(expected_return_pct) * 3, signal_threshold_pct * 4)
        if directional_disagrees or too_wide:
            confidence = _downgrade_confidence(confidence)
            reason += " Quantile uncertainty reduces confidence."

    return TradeSignal(
        signal=side,
        reason=reason,
        current_price=float(current_price),
        forecast_price=forecast_price,
        expected_return_pct=float(expected_return_pct),
        take_profit_price=float(take_profit_price) if take_profit_price is not None else None,
        stop_loss_price=float(stop_loss_price) if stop_loss_price is not None else None,
        confidence_label=confidence,
        signal_horizon_index=selected_index,
    )
