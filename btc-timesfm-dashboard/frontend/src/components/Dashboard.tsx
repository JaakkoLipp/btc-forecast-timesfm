import { useCallback, useEffect, useState } from "react";
import { Cpu, Database, Sparkles } from "lucide-react";
import { getSample, runBacktest, runForecast } from "../api/client";
import { paramsEqual } from "../lib/params";
import type { BacktestRequest, BacktestResponse, ForecastResponse } from "../types";
import { BacktestPanel } from "./BacktestPanel";
import { Disclaimer } from "./Disclaimer";
import { ForecastChart } from "./ForecastChart";
import { ParameterPanel } from "./ParameterPanel";
import { SignalCard } from "./SignalCard";
import { ToastStack, type ToastItem, type ToastTone } from "./ui/Toast";

const defaultParams: BacktestRequest = {
  exchange: "binance",
  symbol: "BTC/USDT",
  timeframe: "5m",
  lookback: 1024,
  horizon: 24,
  target_mode: "log_return",
  use_quantiles: true,
  signal_threshold_pct: 0.5,
  take_profit_pct: 1.0,
  stop_loss_pct: 0.75,
  position_size: 1000,
  fee_pct: 0.1,
  slippage_pct: 0.05,
  allow_short: true,
  signal_horizon_index: null,
  backtest_candles: 1000,
  walk_forward_step: 1,
  max_trades: null,
  allow_overlapping_trades: false,
};

function timeAgo(date: Date | null): string {
  if (!date) return "";
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function Dashboard() {
  const [params, setParams] = useState<BacktestRequest>(defaultParams);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [loadingBacktest, setLoadingBacktest] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [lastForecastParams, setLastForecastParams] = useState<BacktestRequest | null>(null);
  const [lastBacktestParams, setLastBacktestParams] = useState<BacktestRequest | null>(null);
  const [lastForecastAt, setLastForecastAt] = useState<Date | null>(null);
  const [lastBacktestAt, setLastBacktestAt] = useState<Date | null>(null);
  const [usingSample, setUsingSample] = useState(false);
  const [, setTick] = useState(0);

  const pushToast = useCallback((message: string, tone: ToastTone = "error") => {
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2);
    setToasts((current) => [...current, { id, message, tone }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  useEffect(() => {
    getSample()
      .then((sample) => {
        setForecast(sample);
        setUsingSample(true);
      })
      .catch(() => {
        pushToast("Backend not reachable yet. Start FastAPI on http://localhost:8000.");
      });
  }, [pushToast]);

  // Re-render every 30s so "X minutes ago" labels stay fresh.
  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const handleChange = useCallback((patch: Partial<BacktestRequest>) => {
    setParams((current) => ({ ...current, ...patch }));
  }, []);

  const handleReset = useCallback(() => {
    setParams(defaultParams);
    pushToast("Parameters reset to defaults.", "info");
  }, [pushToast]);

  const handleForecast = useCallback(async () => {
    setLoadingForecast(true);
    const ranWith = params;
    try {
      const response = await runForecast(ranWith);
      setForecast(response);
      setUsingSample(false);
      setLastForecastParams(ranWith);
      setLastForecastAt(new Date());
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Forecast request failed.");
    } finally {
      setLoadingForecast(false);
    }
  }, [params, pushToast]);

  const handleBacktest = useCallback(async () => {
    setLoadingBacktest(true);
    const ranWith = params;
    try {
      const response = await runBacktest(ranWith);
      setBacktest(response);
      setLastBacktestParams(ranWith);
      setLastBacktestAt(new Date());
    } catch (err) {
      pushToast(err instanceof Error ? err.message : "Backtest request failed.");
    } finally {
      setLoadingBacktest(false);
    }
  }, [params, pushToast]);

  // Ctrl/Cmd+Enter runs the forecast when nothing else is busy.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        if (!loadingForecast && !loadingBacktest) {
          handleForecast();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleForecast, loadingForecast, loadingBacktest]);

  const forecastStale =
    lastForecastParams !== null && !paramsEqual(params, lastForecastParams);
  const backtestStale =
    lastBacktestParams !== null && !paramsEqual(params, lastBacktestParams);

  const initialEquityForChart = lastBacktestParams?.position_size ?? params.position_size;

  return (
    <div className="min-h-screen bg-ink text-text">
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <div className="grid min-h-screen grid-cols-1 xl:grid-cols-[340px_minmax(0,1fr)]">
        <ParameterPanel
          params={params}
          loadingForecast={loadingForecast}
          loadingBacktest={loadingBacktest}
          forecastStale={forecastStale}
          backtestStale={backtestStale}
          onChange={handleChange}
          onRunForecast={handleForecast}
          onRunBacktest={handleBacktest}
          onReset={handleReset}
        />

        <main className="grid gap-5 p-5">
          <header className="flex flex-col gap-3 rounded-lg border border-line bg-panel p-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xl font-semibold">
                <Sparkles size={20} className="text-accent" />
                Bitcoin Forecasting + Paper Backtesting
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
                <span className="inline-flex items-center gap-1">
                  <Cpu size={13} />
                  CPU-first TimesFM 2.5
                </span>
                <span className="inline-flex items-center gap-1">
                  <Database size={13} />
                  CCXT OHLCV candles
                </span>
                {usingSample ? (
                  <span
                    title="Pre-baked sample data so you can try the UI before fetching real candles. Click Run Forecast to replace it."
                    className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[11px] text-accent"
                  >
                    Demo data
                  </span>
                ) : null}
              </div>
            </div>
          </header>

          <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_380px]">
            <ForecastChart forecast={forecast} backtest={backtest} />
            <div className="grid content-start gap-5">
              <SignalCard
                forecast={forecast}
                stale={forecastStale}
                lastRunAgo={timeAgo(lastForecastAt)}
                isSample={usingSample}
              />
              <Disclaimer />
            </div>
          </div>

          <BacktestPanel
            backtest={backtest}
            lastRunAgo={timeAgo(lastBacktestAt)}
            stale={backtestStale}
            initialEquity={initialEquityForChart}
          />
        </main>
      </div>
    </div>
  );
}
