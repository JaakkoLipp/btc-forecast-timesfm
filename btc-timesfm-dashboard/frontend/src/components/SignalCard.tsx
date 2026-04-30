import type { ReactNode } from "react";
import { ArrowDown, ArrowRight, ArrowUp, Gauge, Info, Target } from "lucide-react";
import type { ForecastResponse, SignalSide } from "../types";
import { FieldHelp } from "./ui/FieldHelp";
import { StaleBadge } from "./ui/StaleBadge";

function money(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(
    value,
  );
}

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return `${value.toFixed(2)}%`;
}

const signalStyle = {
  long: {
    label: "LONG",
    icon: ArrowUp,
    className: "border-positive/40 bg-positive/10 text-positive",
  },
  short: {
    label: "SHORT",
    icon: ArrowDown,
    className: "border-negative/40 bg-negative/10 text-negative",
  },
  hold: {
    label: "HOLD",
    icon: ArrowRight,
    className: "border-line bg-mutedPanel text-muted",
  },
} satisfies Record<SignalSide, { label: string; icon: unknown; className: string }>;

const confidenceClass: Record<string, string> = {
  low: "text-muted",
  medium: "text-accent",
  high: "text-positive",
};

const CONFIDENCE_HELP =
  "Computed from |expected return| ÷ threshold. Wide quantile bands or quantiles disagreeing with the signal direction downgrade the level by one step.";

function StatTile({ label, value, valueClass }: { label: ReactNode; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-line bg-mutedPanel p-3">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-base font-semibold ${valueClass ?? "text-text"}`}>{value}</div>
    </div>
  );
}

interface SignalCardProps {
  forecast: ForecastResponse | null;
  stale?: boolean;
  lastRunAgo?: string;
  isSample?: boolean;
}

export function SignalCard({ forecast, stale = false, lastRunAgo, isSample }: SignalCardProps) {
  if (!forecast) {
    return (
      <section className="rounded-lg border border-line bg-panel p-4">
        <div className="text-sm font-semibold text-text">Theoretical signal</div>
        <div className="mt-4 rounded-lg border border-line bg-mutedPanel p-4 text-sm text-muted">
          Run a forecast to see the model's directional call and a hypothetical PnL estimate.
        </div>
      </section>
    );
  }

  const { signal, mock_estimate } = forecast;
  const style = signalStyle[signal.signal];
  const Icon = style.icon;
  const isTrade = signal.signal !== "hold";

  const expectedReturnClass =
    signal.expected_return_pct >= 0
      ? "text-lg font-semibold text-positive"
      : "text-lg font-semibold text-negative";

  return (
    <section className="rounded-lg border border-line bg-panel p-4 shadow-glow">
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text">Theoretical signal</span>
          <StaleBadge stale={stale} />
          {isSample ? (
            <span className="rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-accent">
              Sample
            </span>
          ) : null}
        </div>
        <div className={`flex items-center gap-2 rounded-md border px-3 py-1 text-sm font-bold ${style.className}`}>
          <Icon size={16} />
          {style.label}
        </div>
      </div>
      <p className="mb-4 text-xs leading-5 text-muted">
        {lastRunAgo ? <span>Last run {lastRunAgo} · </span> : null}
        Direction the model picks at the chosen horizon — not a real order.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-line bg-mutedPanel p-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted">
            <Target size={13} />
            Forecast target
          </div>
          <div className="mt-1 text-lg font-semibold text-text">{money(signal.forecast_price)}</div>
        </div>
        <div className="rounded-lg border border-line bg-mutedPanel p-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted">
            <Gauge size={13} />
            Expected move
          </div>
          <div className={`mt-1 ${expectedReturnClass}`}>{percent(signal.expected_return_pct)}</div>
        </div>
      </div>

      {isTrade ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <StatTile label="Take profit" value={money(signal.take_profit_price)} valueClass="text-positive" />
            <StatTile label="Stop loss" value={money(signal.stop_loss_price)} valueClass="text-negative" />
          </div>

          <div className="mt-4 rounded-lg border border-line bg-mutedPanel p-3">
            <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted">
              <span>If exited at forecast target</span>
              <span
                className={`flex items-center gap-1 font-semibold capitalize ${
                  confidenceClass[signal.confidence_label] ?? "text-muted"
                }`}
              >
                {signal.confidence_label} confidence
                <FieldHelp text={CONFIDENCE_HELP} />
              </span>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
              <div>
                <div className="text-muted">Gross</div>
                <div className="text-sm font-medium text-text">{money(mock_estimate.estimated_gross_pnl)}</div>
              </div>
              <div>
                <div className="text-muted">Fees</div>
                <div className="text-sm font-medium text-text">-{money(mock_estimate.estimated_fees)}</div>
              </div>
              <div>
                <div className="text-muted">Slippage</div>
                <div className="text-sm font-medium text-text">-{money(mock_estimate.estimated_slippage_cost)}</div>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between border-t border-line pt-2">
              <span className="text-xs uppercase tracking-wide text-muted">Net PnL</span>
              <span
                className={
                  mock_estimate.estimated_net_pnl >= 0
                    ? "text-base font-semibold text-positive"
                    : "text-base font-semibold text-negative"
                }
              >
                {money(mock_estimate.estimated_net_pnl)} ({percent(mock_estimate.estimated_return_pct)})
              </span>
            </div>
            <p className="mt-2 flex items-start gap-1 text-[11px] leading-4 text-muted">
              <Info size={12} className="mt-0.5 shrink-0" />
              Assumes the trade exits exactly at the model's forecast price. The walk-forward backtest uses TP/SL/max-hold exits, so per-trade PnL there will differ.
            </p>
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-lg border border-line bg-mutedPanel p-3 text-xs leading-5 text-muted">
          Forecast move is inside the threshold band, so no theoretical trade is opened. TP/SL and PnL only apply when the signal fires.
        </div>
      )}

      <div className="mt-3 rounded-lg border border-line bg-ink p-3 text-xs leading-5 text-muted">
        {signal.reason}
      </div>
      <div className="mt-3 text-xs text-muted">Theoretical signal only, not financial advice.</div>
    </section>
  );
}
