from __future__ import annotations

from uuid import uuid4

from app.schemas import ExitReason, MockEstimate, MockTrade, TradeSide, TradeSignal


def calculate_trade_pnl(
    side: TradeSide,
    entry_price: float,
    exit_price: float,
    position_size: float,
    fee_pct: float,
    slippage_pct: float,
) -> dict[str, float]:
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("entry_price and exit_price must be positive.")
    if position_size <= 0:
        raise ValueError("position_size must be positive.")

    quantity = position_size / entry_price
    if side == "long":
        gross_pnl = quantity * (exit_price - entry_price)
    elif side == "short":
        gross_pnl = quantity * (entry_price - exit_price)
    else:
        raise ValueError(f"Unsupported side '{side}'.")

    exit_notional = quantity * exit_price
    entry_fee = position_size * fee_pct / 100
    exit_fee = exit_notional * fee_pct / 100
    entry_slippage_cost = position_size * slippage_pct / 100
    exit_slippage_cost = exit_notional * slippage_pct / 100
    fees_paid = entry_fee + exit_fee
    slippage_cost = entry_slippage_cost + exit_slippage_cost
    net_pnl = gross_pnl - fees_paid - slippage_cost
    return_pct = (net_pnl / position_size) * 100

    return {
        "quantity": quantity,
        "gross_pnl": gross_pnl,
        "fees_paid": fees_paid,
        "slippage_cost": slippage_cost,
        "net_pnl": net_pnl,
        "return_pct": return_pct,
    }


def estimate_trade_from_signal(
    signal: TradeSignal,
    position_size: float,
    fee_pct: float,
    slippage_pct: float,
) -> MockEstimate:
    if signal.signal == "hold":
        return MockEstimate(
            side="hold",
            entry_price=signal.current_price,
            target_price=None,
            estimated_gross_pnl=0,
            estimated_fees=0,
            estimated_slippage_cost=0,
            estimated_net_pnl=0,
            estimated_return_pct=0,
        )

    pnl = calculate_trade_pnl(
        side=signal.signal,
        entry_price=signal.current_price,
        exit_price=signal.forecast_price,
        position_size=position_size,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
    )
    return MockEstimate(
        side=signal.signal,
        entry_price=signal.current_price,
        target_price=signal.forecast_price,
        estimated_gross_pnl=float(pnl["gross_pnl"]),
        estimated_fees=float(pnl["fees_paid"]),
        estimated_slippage_cost=float(pnl["slippage_cost"]),
        estimated_net_pnl=float(pnl["net_pnl"]),
        estimated_return_pct=float(pnl["return_pct"]),
    )


def close_trade(
    side: TradeSide,
    entry_time: str,
    exit_time: str,
    entry_price: float,
    exit_price: float,
    position_size: float,
    fee_pct: float,
    slippage_pct: float,
    exit_reason: ExitReason,
    holding_candles: int,
    trade_id: str | None = None,
) -> MockTrade:
    pnl = calculate_trade_pnl(
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        position_size=position_size,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
    )
    return MockTrade(
        id=trade_id or str(uuid4()),
        side=side,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        position_size=float(position_size),
        quantity=float(pnl["quantity"]),
        gross_pnl=float(pnl["gross_pnl"]),
        fees_paid=float(pnl["fees_paid"]),
        slippage_cost=float(pnl["slippage_cost"]),
        net_pnl=float(pnl["net_pnl"]),
        return_pct=float(pnl["return_pct"]),
        exit_reason=exit_reason,
        holding_candles=int(holding_candles),
    )

