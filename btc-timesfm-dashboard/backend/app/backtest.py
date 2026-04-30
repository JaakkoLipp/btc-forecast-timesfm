from __future__ import annotations

import numpy as np
import pandas as pd

from app.data import validate_ohlcv_frame
from app.mock_trading import close_trade
from app.schemas import (
    BacktestBaseline,
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    EquityPoint,
    MockTrade,
    TradeSignal,
)
from app.signals import generate_trade_signal


def simulate_trade_exit(
    signal: TradeSignal,
    future_candles: pd.DataFrame,
) -> tuple[float, str, str, int]:
    if signal.signal not in {"long", "short"}:
        raise ValueError("simulate_trade_exit requires a long or short signal.")
    if future_candles.empty:
        raise ValueError("future_candles cannot be empty.")

    side = signal.signal
    take_profit = signal.take_profit_price
    stop_loss = signal.stop_loss_price
    if take_profit is None or stop_loss is None:
        raise ValueError("take-profit and stop-loss prices are required.")

    for offset, row in enumerate(future_candles.itertuples(index=False), start=1):
        high = float(row.high)
        low = float(row.low)
        if side == "long":
            stop_hit = low <= stop_loss
            target_hit = high >= take_profit
        else:
            stop_hit = high >= stop_loss
            target_hit = low <= take_profit

        if stop_hit:
            return float(stop_loss), str(row.datetime), "stop_loss", offset
        if target_hit:
            return float(take_profit), str(row.datetime), "take_profit", offset

    last = future_candles.iloc[-1]
    return float(last["close"]), str(last["datetime"]), "max_hold", len(future_candles)


def calculate_metrics(
    trades: list[MockTrade],
    equity_curve: list[EquityPoint],
    initial_equity: float,
    directional_correct: int = 0,
    directional_total: int = 0,
) -> BacktestMetrics:
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_pnl = sum(trade.gross_pnl for trade in trades)
    net_pnl = sum(trade.net_pnl for trade in trades)
    fees_paid = sum(trade.fees_paid for trade in trades)
    slippage_paid = sum(trade.slippage_cost for trade in trades)
    gross_wins = sum(trade.net_pnl for trade in wins)
    gross_losses = abs(sum(trade.net_pnl for trade in losses))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else (999_999.0 if gross_wins > 0 else 0)
    average_win = gross_wins / len(wins) if wins else 0
    average_loss = -gross_losses / len(losses) if losses else 0
    final_equity = initial_equity + net_pnl

    max_drawdown = 0.0
    peak = initial_equity
    for point in equity_curve:
        peak = max(peak, point.equity)
        max_drawdown = max(max_drawdown, peak - point.equity)

    return BacktestMetrics(
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=(len(wins) / len(trades) * 100) if trades else 0,
        gross_pnl=float(gross_pnl),
        net_pnl=float(net_pnl),
        fees_paid=float(fees_paid),
        slippage_paid=float(slippage_paid),
        average_win=float(average_win),
        average_loss=float(average_loss),
        profit_factor=float(profit_factor),
        max_drawdown=float(max_drawdown),
        final_equity=float(final_equity),
        return_pct=float((net_pnl / initial_equity) * 100 if initial_equity else 0),
        directional_accuracy_pct=float(
            (directional_correct / directional_total) * 100 if directional_total else 0
        ),
    )


def calculate_baseline(
    frame: pd.DataFrame,
    trades: list[MockTrade],
    request: BacktestRequest,
    naive_directional_correct: int,
    naive_directional_total: int,
) -> BacktestBaseline:
    if len(frame) < 2:
        buy_hold_return_pct = 0.0
    else:
        first = float(frame.iloc[0]["close"])
        last = float(frame.iloc[-1]["close"])
        buy_hold_return_pct = ((last - first) / first) * 100 if first else 0

    strategy_return_pct = (sum(trade.net_pnl for trade in trades) / request.position_size) * 100
    return BacktestBaseline(
        buy_and_hold_pnl=float(request.position_size * buy_hold_return_pct / 100),
        buy_and_hold_return_pct=float(buy_hold_return_pct),
        naive_directional_accuracy_pct=float(
            (naive_directional_correct / naive_directional_total) * 100
            if naive_directional_total
            else 0
        ),
        strategy_vs_buy_hold_pct=float(strategy_return_pct - buy_hold_return_pct),
    )


def run_walk_forward_backtest(
    candles: pd.DataFrame,
    request: BacktestRequest,
    forecaster,
) -> BacktestResponse:
    frame = validate_ohlcv_frame(candles)
    minimum = request.lookback + request.horizon
    if len(frame) < minimum:
        raise ValueError(f"Backtest requires at least {minimum} candles; got {len(frame)}.")

    start = max(request.lookback, len(frame) - request.backtest_candles - request.horizon)
    end = len(frame) - request.horizon
    trades: list[MockTrade] = []
    equity_curve: list[EquityPoint] = [
        EquityPoint(
            timestamp=int(frame.iloc[start - 1]["timestamp"]),
            datetime=str(frame.iloc[start - 1]["datetime"]),
            equity=float(request.position_size),
        )
    ]
    equity = float(request.position_size)
    warnings: list[str] = []
    estimated_windows = max(0, (end - start + request.walk_forward_step - 1) // request.walk_forward_step)
    if estimated_windows > 250:
        warnings.append(
            f"Backtest evaluated up to {estimated_windows} forecast windows. "
            "Real TimesFM CPU backtests can be slow; increase walk step or set max trades "
            "for quicker iteration."
        )
    directional_correct = 0
    directional_total = 0
    naive_directional_correct = 0
    naive_directional_total = 0
    last_exit_index = -1
    index = start

    while index < end:
        if not request.allow_overlapping_trades and index <= last_exit_index:
            index = last_exit_index + 1
            continue

        context = frame.iloc[index - request.lookback : index]
        current = context.iloc[-1]
        future = frame.iloc[index : index + request.horizon]
        computation = forecaster.forecast(
            close_prices=context["close"].to_numpy(),
            horizon=request.horizon,
            target_mode=request.target_mode,
            use_quantiles=request.use_quantiles,
        )
        if computation.warnings:
            warnings.extend(w for w in computation.warnings if w not in warnings)

        forecast = computation.result
        signal = generate_trade_signal(
            current_price=float(current["close"]),
            forecast_prices=forecast.predicted_prices,
            signal_horizon_index=request.signal_horizon_index,
            signal_threshold_pct=request.signal_threshold_pct,
            take_profit_pct=request.take_profit_pct,
            stop_loss_pct=request.stop_loss_pct,
            allow_short=request.allow_short,
            quantiles=forecast.quantiles,
        )

        actual_index = min(signal.signal_horizon_index, len(future) - 1)
        actual_close = float(future.iloc[actual_index]["close"])
        predicted_direction = np.sign(signal.forecast_price - signal.current_price)
        actual_direction = np.sign(actual_close - signal.current_price)
        naive_directional_total += 1
        if actual_direction == 0:
            naive_directional_correct += 1
        if predicted_direction != 0 and actual_direction != 0:
            directional_total += 1
            if predicted_direction == actual_direction:
                directional_correct += 1

        if signal.signal == "hold":
            index += request.walk_forward_step
            continue

        exit_price, exit_time, exit_reason, holding_candles = simulate_trade_exit(signal, future)
        trade = close_trade(
            side=signal.signal,
            entry_time=str(current["datetime"]),
            exit_time=exit_time,
            entry_price=float(current["close"]),
            exit_price=exit_price,
            position_size=request.position_size,
            fee_pct=request.fee_pct,
            slippage_pct=request.slippage_pct,
            exit_reason=exit_reason,
            holding_candles=holding_candles,
        )
        trades.append(trade)
        equity += trade.net_pnl
        exit_candle_index = index + holding_candles - 1
        last_exit_index = max(last_exit_index, exit_candle_index)
        exit_timestamp = int(frame.iloc[min(exit_candle_index, len(frame) - 1)]["timestamp"])
        equity_curve.append(EquityPoint(timestamp=exit_timestamp, datetime=exit_time, equity=float(equity)))

        if request.max_trades and len(trades) >= request.max_trades:
            break

        index = index + request.walk_forward_step if request.allow_overlapping_trades else last_exit_index + 1

    metrics = calculate_metrics(
        trades=trades,
        equity_curve=equity_curve,
        initial_equity=request.position_size,
        directional_correct=directional_correct,
        directional_total=directional_total,
    )
    baseline = calculate_baseline(
        frame=frame.iloc[start:end],
        trades=trades,
        request=request,
        naive_directional_correct=naive_directional_correct,
        naive_directional_total=naive_directional_total,
    )
    return BacktestResponse(
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
        baseline=baseline,
        warnings=warnings,
    )
