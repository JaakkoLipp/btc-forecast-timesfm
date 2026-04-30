from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetMode = Literal["close", "log_return"]
SignalSide = Literal["long", "short", "hold"]
TradeSide = Literal["long", "short"]
ExitReason = Literal["take_profit", "stop_loss", "max_hold", "signal_flip", "end_of_data"]


class Candle(BaseModel):
    timestamp: int
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class ForecastRequest(BaseModel):
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "5m"
    lookback: int = Field(default=1024, ge=20, le=16000)
    horizon: int = Field(default=24, ge=1, le=1000)
    target_mode: TargetMode = "log_return"
    use_quantiles: bool = True
    signal_threshold_pct: float = Field(default=0.5, ge=0)
    take_profit_pct: float = Field(default=1.0, ge=0)
    stop_loss_pct: float = Field(default=0.75, ge=0)
    position_size: float = Field(default=1000.0, gt=0)
    fee_pct: float = Field(default=0.1, ge=0)
    slippage_pct: float = Field(default=0.05, ge=0)
    allow_short: bool = True
    signal_horizon_index: int | None = Field(default=None, ge=0)


class ForecastQuantile(BaseModel):
    horizon_index: int
    timestamp: int | None = None
    datetime: str | None = None
    lower: float
    median: float | None = None
    upper: float
    mean: float | None = None


class ForecastResult(BaseModel):
    predicted_prices: list[float]
    predicted_target_values: list[float]
    quantiles: list[ForecastQuantile] | None = None
    last_price: float
    target_mode: TargetMode
    timestamps: list[int] = Field(default_factory=list)
    datetimes: list[str] = Field(default_factory=list)


class TradeSignal(BaseModel):
    signal: SignalSide
    reason: str
    current_price: float
    forecast_price: float
    expected_return_pct: float
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    confidence_label: Literal["low", "medium", "high"]
    signal_horizon_index: int


class MockEstimate(BaseModel):
    side: SignalSide
    entry_price: float
    target_price: float | None = None
    estimated_gross_pnl: float
    estimated_fees: float
    estimated_slippage_cost: float
    estimated_net_pnl: float
    estimated_return_pct: float


class ForecastResponse(BaseModel):
    request: ForecastRequest
    candles: list[Candle]
    forecast: ForecastResult
    signal: TradeSignal
    mock_estimate: MockEstimate
    warnings: list[str] = Field(default_factory=list)


class BacktestRequest(ForecastRequest):
    backtest_candles: int = Field(default=1000, ge=50, le=16000)
    walk_forward_step: int = Field(default=1, ge=1, le=500)
    max_trades: int | None = Field(default=None, ge=1)
    allow_overlapping_trades: bool = False


class MockTrade(BaseModel):
    id: str
    side: TradeSide
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    position_size: float
    quantity: float
    gross_pnl: float
    fees_paid: float
    slippage_cost: float
    net_pnl: float
    return_pct: float
    exit_reason: ExitReason
    holding_candles: int


class EquityPoint(BaseModel):
    timestamp: int
    datetime: str
    equity: float


class BacktestMetrics(BaseModel):
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    gross_pnl: float
    net_pnl: float
    fees_paid: float
    slippage_paid: float
    average_win: float
    average_loss: float
    profit_factor: float
    max_drawdown: float
    final_equity: float
    return_pct: float
    directional_accuracy_pct: float


class BacktestBaseline(BaseModel):
    buy_and_hold_pnl: float
    buy_and_hold_return_pct: float
    naive_directional_accuracy_pct: float
    strategy_vs_buy_hold_pct: float


class BacktestResponse(BaseModel):
    trades: list[MockTrade]
    equity_curve: list[EquityPoint]
    metrics: BacktestMetrics
    baseline: BacktestBaseline
    warnings: list[str] = Field(default_factory=list)


class MetadataResponse(BaseModel):
    supported_exchanges: list[str]
    supported_symbols: list[str]
    supported_timeframes: list[str]
    defaults: dict[str, str | int | float | bool]
    model: dict[str, str | int | bool]
    disclaimer: str

    model_config = ConfigDict(protected_namespaces=())

