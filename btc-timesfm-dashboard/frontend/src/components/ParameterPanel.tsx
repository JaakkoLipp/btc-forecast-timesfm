import {
  Activity,
  BarChart3,
  Database,
  Layers,
  Play,
  Repeat,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Target,
} from "lucide-react";
import type { BacktestRequest, TargetMode } from "../types";
import { FieldHelp } from "./ui/FieldHelp";
import { Section } from "./ui/Section";
import { StaleBadge } from "./ui/StaleBadge";

interface ParameterPanelProps {
  params: BacktestRequest;
  loadingForecast: boolean;
  loadingBacktest: boolean;
  forecastStale: boolean;
  backtestStale: boolean;
  onChange: (patch: Partial<BacktestRequest>) => void;
  onRunForecast: () => void;
  onRunBacktest: () => void;
  onReset: () => void;
}

function parseNumeric(raw: string): number | null {
  if (raw.trim() === "") return null;
  const normalized = raw.replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function FieldLabel({ label, help }: { label: string; help?: string }) {
  return (
    <span className="flex items-center gap-1.5">
      {label}
      {help ? <FieldHelp text={help} /> : null}
    </span>
  );
}

interface NumberInputProps {
  label: string;
  help?: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}

function NumberInput({ label, help, value, min, max, step, onChange }: NumberInputProps) {
  const isInteger = step === undefined || Number.isInteger(step);
  return (
    <label className="grid gap-1 text-sm text-muted">
      <FieldLabel label={label} help={help} />
      <input
        className="h-10 w-full min-w-0 rounded-md border border-line bg-ink px-3 text-sm text-text outline-none transition focus:border-accent"
        type="number"
        inputMode={isInteger ? "numeric" : "decimal"}
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const parsed = parseNumeric(event.target.value);
          if (parsed === null) return;
          onChange(parsed);
        }}
      />
    </label>
  );
}

interface SelectInputProps<T extends string> {
  label: string;
  help?: string;
  value: T;
  values: T[];
  onChange: (value: T) => void;
}

function SelectInput<T extends string>({ label, help, value, values, onChange }: SelectInputProps<T>) {
  return (
    <label className="grid gap-1 text-sm text-muted">
      <FieldLabel label={label} help={help} />
      <select
        className="h-10 rounded-md border border-line bg-ink px-3 text-sm text-text outline-none transition focus:border-accent"
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
      >
        {values.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </label>
  );
}

interface OptionalNumberInputProps {
  label: string;
  help?: string;
  value: number | null;
  min?: number;
  step?: number;
  onChange: (value: number | null) => void;
}

function OptionalNumberInput({ label, help, value, min, step, onChange }: OptionalNumberInputProps) {
  const isInteger = step === undefined || Number.isInteger(step);
  return (
    <label className="grid gap-1 text-sm text-muted">
      <FieldLabel label={label} help={help} />
      <input
        className="h-10 w-full min-w-0 rounded-md border border-line bg-ink px-3 text-sm text-text outline-none transition focus:border-accent"
        type="number"
        inputMode={isInteger ? "numeric" : "decimal"}
        value={value ?? ""}
        min={min}
        step={step}
        placeholder="Auto"
        onChange={(event) => {
          const rawValue = event.target.value;
          if (rawValue.trim() === "") {
            onChange(null);
            return;
          }
          const parsed = parseNumeric(rawValue);
          if (parsed === null) return;
          onChange(parsed);
        }}
      />
    </label>
  );
}

interface ToggleInputProps {
  label: string;
  help?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleInput({ label, help, checked, onChange }: ToggleInputProps) {
  return (
    <label className="flex items-center justify-between rounded-lg border border-line bg-mutedPanel px-3 py-2 text-sm text-muted">
      <FieldLabel label={label} help={help} />
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

const isMac = typeof navigator !== "undefined" && /mac/i.test(navigator.platform);
const runShortcut = isMac ? "⌘ ↵" : "Ctrl ↵";

export function ParameterPanel({
  params,
  loadingForecast,
  loadingBacktest,
  forecastStale,
  backtestStale,
  onChange,
  onRunForecast,
  onRunBacktest,
  onReset,
}: ParameterPanelProps) {
  const disabled = loadingForecast || loadingBacktest;

  return (
    <aside className="flex flex-col gap-3 border-r border-line bg-panel p-4 xl:sticky xl:top-0 xl:h-screen xl:overflow-y-auto">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-lg font-semibold text-text">
            <Activity size={20} className="text-accent" />
            BTC TimesFM
          </div>
          <p className="mt-1 text-[11px] leading-4 text-muted">
            First real forecast may take 10–60s while TimesFM loads on CPU.
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          disabled={disabled}
          className="flex items-center gap-1 rounded-md border border-line bg-mutedPanel px-2 py-1 text-[11px] text-muted transition hover:border-accent hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
          title="Reset all parameters to defaults"
        >
          <RotateCcw size={11} />
          Reset
        </button>
      </div>

      <Section
        title="Market"
        icon={<Database size={12} className="text-muted" />}
        description="Where to fetch OHLCV candles from."
      >
        <SelectInput
          label="Exchange"
          help="CCXT exchange ID. Spot markets only."
          value={params.exchange}
          values={["binance", "coinbase", "kraken"]}
          onChange={(exchange) => onChange({ exchange })}
        />
        <label className="grid gap-1 text-sm text-muted">
          <FieldLabel label="Symbol" help="Market pair as the exchange names it, e.g. BTC/USDT, BTC/USD." />
          <input
            className="h-10 rounded-md border border-line bg-ink px-3 text-sm text-text outline-none transition focus:border-accent"
            value={params.symbol}
            onChange={(event) => onChange({ symbol: event.target.value })}
          />
        </label>
        <SelectInput
          label="Timeframe"
          help="Candle interval. Smaller = more noise, larger = fewer signals."
          value={params.timeframe}
          values={["1m", "5m", "15m", "1h", "4h", "1d"]}
          onChange={(timeframe) => onChange({ timeframe })}
        />
      </Section>

      <Section
        title="Model"
        icon={<Layers size={12} className="text-muted" />}
        description="What TimesFM is asked to predict and how much history it sees."
      >
        <SelectInput<TargetMode>
          label="Target"
          help="log_return is usually more stable. close predicts the price level directly."
          value={params.target_mode}
          values={["log_return", "close"]}
          onChange={(target_mode) => onChange({ target_mode })}
        />
        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label="Lookback"
            help="Number of past candles fed into the model. Capped by the model's max context (2048)."
            value={params.lookback}
            min={20}
            max={2048}
            step={1}
            onChange={(lookback) => onChange({ lookback })}
          />
          <NumberInput
            label="Horizon"
            help="How many future candles to forecast. Capped by the model's max horizon (256)."
            value={params.horizon}
            min={1}
            max={256}
            step={1}
            onChange={(horizon) => onChange({ horizon })}
          />
        </div>
        <ToggleInput
          label="Use quantiles"
          help="Render uncertainty bands and downgrade signal confidence when the band disagrees with the direction."
          checked={params.use_quantiles}
          onChange={(use_quantiles) => onChange({ use_quantiles })}
        />
      </Section>

      <Section
        title="Signal"
        icon={<Target size={12} className="text-muted" />}
        description="When does the forecast turn into a long or short call."
      >
        <NumberInput
          label="Threshold %"
          help="Minimum |expected return| needed to fire a signal. Below this band the signal is HOLD."
          value={params.signal_threshold_pct}
          min={0}
          step={0.05}
          onChange={(signal_threshold_pct) => onChange({ signal_threshold_pct })}
        />
        <ToggleInput
          label="Allow shorts"
          help="If off, negative-expected-return forecasts become HOLD instead of SHORT."
          checked={params.allow_short}
          onChange={(allow_short) => onChange({ allow_short })}
        />
        <OptionalNumberInput
          label="Signal index"
          help="Which forecast step to read the signal from (0 = next candle). Auto uses the last horizon step."
          value={params.signal_horizon_index}
          min={0}
          step={1}
          onChange={(signal_horizon_index) => onChange({ signal_horizon_index })}
        />
      </Section>

      <Section
        title="Risk & sizing"
        icon={<ShieldAlert size={12} className="text-muted" />}
        description="Per-trade exit levels and cost model."
      >
        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label="Take profit %"
            help="Distance from entry where a winning trade closes."
            value={params.take_profit_pct}
            min={0}
            step={0.05}
            onChange={(take_profit_pct) => onChange({ take_profit_pct })}
          />
          <NumberInput
            label="Stop loss %"
            help="Distance from entry where a losing trade closes."
            value={params.stop_loss_pct}
            min={0}
            step={0.05}
            onChange={(stop_loss_pct) => onChange({ stop_loss_pct })}
          />
        </div>
        <NumberInput
          label="Position $"
          help="Notional size of each hypothetical trade. PnL and fees scale with this."
          value={params.position_size}
          min={1}
          step={50}
          onChange={(position_size) => onChange({ position_size })}
        />
        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label="Fee %"
            help="Round-trip trading fee per side."
            value={params.fee_pct}
            min={0}
            step={0.01}
            onChange={(fee_pct) => onChange({ fee_pct })}
          />
          <NumberInput
            label="Slippage %"
            help="Assumed adverse price impact at entry and exit."
            value={params.slippage_pct}
            min={0}
            step={0.01}
            onChange={(slippage_pct) => onChange({ slippage_pct })}
          />
        </div>
      </Section>

      <Section
        title="Backtest"
        icon={<Repeat size={12} className="text-muted" />}
        description="Walk-forward replay settings. Larger ranges + smaller walk step = slower."
        defaultOpen={false}
      >
        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label="Backtest candles"
            help="How many recent candles to replay. Each one is a potential trade entry."
            value={params.backtest_candles}
            min={50}
            max={16000}
            step={50}
            onChange={(backtest_candles) => onChange({ backtest_candles })}
          />
          <NumberInput
            label="Walk step"
            help="Stride between forecast windows. 1 = every candle, 5 = every 5th, etc."
            value={params.walk_forward_step}
            min={1}
            step={1}
            onChange={(walk_forward_step) => onChange({ walk_forward_step })}
          />
        </div>
        <OptionalNumberInput
          label="Max trades"
          help="Stop the backtest after this many trades. Auto = unbounded."
          value={params.max_trades}
          min={1}
          step={1}
          onChange={(max_trades) => onChange({ max_trades })}
        />
        <ToggleInput
          label="Overlapping trades"
          help="If on, new trades can open while a previous one is still in flight."
          checked={params.allow_overlapping_trades}
          onChange={(allow_overlapping_trades) => onChange({ allow_overlapping_trades })}
        />
      </Section>

      <div className="mt-auto grid gap-2 pt-2">
        <button
          className="relative flex h-11 items-center justify-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-ink transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
          onClick={onRunForecast}
          type="button"
          title={`Run forecast (${runShortcut})`}
        >
          {loadingForecast ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
          Run Forecast
          <kbd className="hidden rounded bg-ink/30 px-1.5 py-0.5 text-[10px] font-medium text-ink/70 sm:inline">
            {runShortcut}
          </kbd>
          {forecastStale ? (
            <span className="absolute right-2 top-1.5">
              <StaleBadge stale label="Stale" />
            </span>
          ) : null}
        </button>
        <button
          className="relative flex h-9 items-center justify-center gap-2 rounded-md border border-line bg-mutedPanel px-3 text-xs font-semibold text-muted transition hover:border-accent hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
          onClick={onRunBacktest}
          type="button"
        >
          {loadingBacktest ? <RefreshCw size={14} className="animate-spin" /> : <BarChart3 size={14} />}
          Run Backtest
          {backtestStale ? (
            <span className="absolute right-2 top-1">
              <StaleBadge stale label="Stale" />
            </span>
          ) : null}
        </button>
      </div>
    </aside>
  );
}
