import { ListChecks } from "lucide-react";
import type { BacktestResponse } from "../types";
import { EquityCurve } from "./EquityCurve";
import { MetricCard } from "./MetricCard";
import { StaleBadge } from "./ui/StaleBadge";

function money(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function pct(value: number) {
  return `${value.toFixed(2)}%`;
}

function tone(value: number) {
  if (value > 0) return "positive" as const;
  if (value < 0) return "negative" as const;
  return "neutral" as const;
}

function profitFactor(value: number) {
  if (!Number.isFinite(value) || value >= 999_999) return "∞";
  return value.toFixed(2);
}

const EXIT_REASON_LABELS: Record<string, string> = {
  take_profit: "Take profit",
  stop_loss: "Stop loss",
  max_hold: "Max hold",
  signal_flip: "Signal flip",
  end_of_data: "End of data",
};

const EXIT_REASON_TONE: Record<string, string> = {
  take_profit: "text-positive",
  stop_loss: "text-negative",
  max_hold: "text-muted",
  signal_flip: "text-muted",
  end_of_data: "text-muted",
};

function formatExitReason(reason: string) {
  return EXIT_REASON_LABELS[reason] ?? reason;
}

function formatTime(iso: string) {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return iso;
  const date = new Date(parsed);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

interface BacktestPanelProps {
  backtest: BacktestResponse | null;
  lastRunAgo?: string;
  stale?: boolean;
  initialEquity: number;
}

export function BacktestPanel({ backtest, lastRunAgo, stale = false, initialEquity }: BacktestPanelProps) {
  return (
    <section className="rounded-lg border border-line bg-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-text">
          <ListChecks size={16} className="text-accent" />
          Walk-forward Backtest
          <StaleBadge stale={stale} />
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          {backtest ? (
            <>
              {lastRunAgo ? <span>Updated {lastRunAgo}</span> : null}
              {lastRunAgo ? <span aria-hidden>·</span> : null}
              <span>{backtest.trades.length} mock trades</span>
            </>
          ) : (
            <span>No run yet</span>
          )}
        </div>
      </div>

      {backtest ? (
        <div className="grid gap-4 p-4">
          {backtest.warnings.length ? (
            <div className="rounded-lg border border-negative/30 bg-negative/10 px-3 py-2 text-sm text-orange-100">
              {backtest.warnings[0]}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 2xl:grid-cols-7">
            <MetricCard label="Net PnL" value={money(backtest.metrics.net_pnl)} tone={tone(backtest.metrics.net_pnl)} />
            <MetricCard label="Win rate" value={pct(backtest.metrics.win_rate_pct)} tone="accent" />
            <MetricCard label="Trades" value={String(backtest.metrics.total_trades)} />
            <MetricCard label="Max drawdown" value={money(backtest.metrics.max_drawdown)} tone="negative" />
            <MetricCard label="Profit factor" value={profitFactor(backtest.metrics.profit_factor)} />
            <MetricCard label="Fees paid" value={money(backtest.metrics.fees_paid)} />
            <MetricCard
              label="Vs buy-hold"
              value={pct(backtest.baseline.strategy_vs_buy_hold_pct)}
              tone={tone(backtest.baseline.strategy_vs_buy_hold_pct)}
            />
          </div>

          <EquityCurve backtest={backtest} initialEquity={initialEquity} />

          <p className="text-xs leading-5 text-muted">
            Each row is a hypothetical trade opened when the model's signal fired. Exit price is the first TP/SL hit
            inside the horizon window, or the close at max-hold if neither triggered. Fees and slippage are deducted
            using the same rates as the side panel.
          </p>

          <div className="overflow-hidden rounded-lg border border-line">
            <div className="max-h-72 overflow-auto">
              <table className="min-w-full divide-y divide-line text-sm">
                <thead className="sticky top-0 bg-mutedPanel text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-3 py-3 text-left">Side</th>
                    <th className="px-3 py-3 text-left">Entry</th>
                    <th className="px-3 py-3 text-left">Exit</th>
                    <th className="px-3 py-3 text-right">Entry price</th>
                    <th className="px-3 py-3 text-right">Exit price</th>
                    <th className="px-3 py-3 text-right">Hold</th>
                    <th className="px-3 py-3 text-right">Net PnL</th>
                    <th className="px-3 py-3 text-right">Return</th>
                    <th className="px-3 py-3 text-left">Exit reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line bg-ink/40">
                  {backtest.trades.length === 0 ? (
                    <tr>
                      <td className="px-3 py-4 text-muted" colSpan={9}>
                        No trades met the signal threshold. Lower the threshold or widen lookback/horizon to surface more setups.
                      </td>
                    </tr>
                  ) : (
                    backtest.trades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-mutedPanel/60">
                        <td className={trade.side === "long" ? "px-3 py-3 font-medium text-positive" : "px-3 py-3 font-medium text-negative"}>
                          {trade.side.toUpperCase()}
                        </td>
                        <td className="px-3 py-3 text-muted" title={trade.entry_time}>{formatTime(trade.entry_time)}</td>
                        <td className="px-3 py-3 text-muted" title={trade.exit_time}>{formatTime(trade.exit_time)}</td>
                        <td className="px-3 py-3 text-right text-text">{money(trade.entry_price)}</td>
                        <td className="px-3 py-3 text-right text-text">{money(trade.exit_price)}</td>
                        <td className="px-3 py-3 text-right text-muted">{trade.holding_candles}</td>
                        <td className={trade.net_pnl >= 0 ? "px-3 py-3 text-right text-positive" : "px-3 py-3 text-right text-negative"}>
                          {money(trade.net_pnl)}
                        </td>
                        <td className={trade.return_pct >= 0 ? "px-3 py-3 text-right text-positive" : "px-3 py-3 text-right text-negative"}>
                          {pct(trade.return_pct)}
                        </td>
                        <td className={`px-3 py-3 ${EXIT_REASON_TONE[trade.exit_reason] ?? "text-muted"}`}>
                          {formatExitReason(trade.exit_reason)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 text-sm text-muted">Run a backtest to populate mock trade metrics and the trade ledger.</div>
      )}
    </section>
  );
}
