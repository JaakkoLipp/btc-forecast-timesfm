export type TargetMode = "close" | "log_return";
export type SignalSide = "long" | "short" | "hold";
export type TradeSide = "long" | "short";

export interface Candle {
  timestamp: number;
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ForecastRequest {
  exchange: string;
  symbol: string;
  timeframe: string;
  lookback: number;
  horizon: number;
  target_mode: TargetMode;
  use_quantiles: boolean;
  signal_threshold_pct: number;
  take_profit_pct: number;
  stop_loss_pct: number;
  position_size: number;
  fee_pct: number;
  slippage_pct: number;
  allow_short: boolean;
  signal_horizon_index: number | null;
}

export interface ForecastQuantile {
  horizon_index: number;
  timestamp: number | null;
  datetime: string | null;
  lower: number;
  median: number | null;
  upper: number;
  mean: number | null;
}

export interface ForecastResult {
  predicted_prices: number[];
  predicted_target_values: number[];
  quantiles: ForecastQuantile[] | null;
  last_price: number;
  target_mode: TargetMode;
  timestamps: number[];
  datetimes: string[];
}

export interface TradeSignal {
  signal: SignalSide;
  reason: string;
  current_price: number;
  forecast_price: number;
  expected_return_pct: number;
  take_profit_price: number | null;
  stop_loss_price: number | null;
  confidence_label: "low" | "medium" | "high";
  signal_horizon_index: number;
}

export interface MockEstimate {
  side: SignalSide;
  entry_price: number;
  target_price: number | null;
  estimated_gross_pnl: number;
  estimated_fees: number;
  estimated_slippage_cost: number;
  estimated_net_pnl: number;
  estimated_return_pct: number;
}

export interface ForecastResponse {
  request: ForecastRequest;
  candles: Candle[];
  forecast: ForecastResult;
  signal: TradeSignal;
  mock_estimate: MockEstimate;
  warnings: string[];
}

export interface BacktestRequest extends ForecastRequest {
  backtest_candles: number;
  walk_forward_step: number;
  max_trades: number | null;
  allow_overlapping_trades: boolean;
}

export interface MockTrade {
  id: string;
  side: TradeSide;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  position_size: number;
  quantity: number;
  gross_pnl: number;
  fees_paid: number;
  slippage_cost: number;
  net_pnl: number;
  return_pct: number;
  exit_reason: string;
  holding_candles: number;
}

export interface EquityPoint {
  timestamp: number;
  datetime: string;
  equity: number;
}

export interface BacktestMetrics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  gross_pnl: number;
  net_pnl: number;
  fees_paid: number;
  slippage_paid: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  max_drawdown: number;
  final_equity: number;
  return_pct: number;
  directional_accuracy_pct: number;
}

export interface BacktestBaseline {
  buy_and_hold_pnl: number;
  buy_and_hold_return_pct: number;
  naive_directional_accuracy_pct: number;
  strategy_vs_buy_hold_pct: number;
}

export interface BacktestResponse {
  trades: MockTrade[];
  equity_curve: EquityPoint[];
  metrics: BacktestMetrics;
  baseline: BacktestBaseline;
  warnings: string[];
}

