import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts";
import type { BacktestResponse, Candle, ForecastResponse } from "../types";

interface ForecastChartProps {
  forecast: ForecastResponse | null;
  backtest: BacktestResponse | null;
}

function toChartTime(timestampMs: number): UTCTimestamp {
  return Math.floor(timestampMs / 1000) as UTCTimestamp;
}

function isoToChartTime(iso: string): UTCTimestamp {
  return Math.floor(Date.parse(iso) / 1000) as UTCTimestamp;
}

function money(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function candleData(candles: Candle[]) {
  return candles.map((candle) => ({
    time: toChartTime(candle.timestamp),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }));
}

export function ForecastChart({ forecast, backtest }: ForecastChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!chartRef.current || !forecast || forecast.candles.length === 0) return;

    const chart = createChart(chartRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0B1020" },
        textColor: "#94A3B8",
        fontFamily: "Inter, ui-sans-serif, system-ui",
      },
      grid: {
        vertLines: { color: "rgba(31, 41, 55, 0.55)" },
        horzLines: { color: "rgba(31, 41, 55, 0.55)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: "#1F2937",
      },
      timeScale: {
        borderColor: "#1F2937",
        timeVisible: true,
      },
    });

    const candles = candleData(forecast.candles);
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22C55E",
      downColor: "#F97316",
      borderVisible: false,
      wickUpColor: "#22C55E",
      wickDownColor: "#F97316",
    });
    candleSeries.setData(candles);

    const lastCandle = forecast.candles[forecast.candles.length - 1];
    const lastTime = toChartTime(lastCandle.timestamp);
    const forecastData = [
      { time: lastTime, value: lastCandle.close },
      ...forecast.forecast.timestamps.map((timestamp, index) => ({
        time: toChartTime(timestamp),
        value: forecast.forecast.predicted_prices[index],
      })),
    ];

    const forecastSeries = chart.addLineSeries({
      color: "#22D3EE",
      lineWidth: 3,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    forecastSeries.setData(forecastData);

    if (forecast.forecast.quantiles?.length) {
      const upperData = forecast.forecast.quantiles
        .filter((q) => q.timestamp)
        .map((q) => ({ time: toChartTime(q.timestamp as number), value: q.upper }));
      const lowerData = forecast.forecast.quantiles
        .filter((q) => q.timestamp)
        .map((q) => ({ time: toChartTime(q.timestamp as number), value: q.lower }));

      const areaSeries = chart.addAreaSeries({
        topColor: "rgba(34, 211, 238, 0.08)",
        bottomColor: "rgba(34, 211, 238, 0.00)",
        lineColor: "rgba(34, 211, 238, 0.00)",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      areaSeries.setData(upperData);

      const upperSeries = chart.addLineSeries({
        color: "rgba(34, 211, 238, 0.45)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      upperSeries.setData(upperData);

      const lowerSeries = chart.addLineSeries({
        color: "rgba(34, 211, 238, 0.45)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      lowerSeries.setData(lowerData);
    }

    if (forecast.signal.take_profit_price) {
      candleSeries.createPriceLine({
        price: forecast.signal.take_profit_price,
        color: "#22C55E",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "TP",
      });
    }
    if (forecast.signal.stop_loss_price) {
      candleSeries.createPriceLine({
        price: forecast.signal.stop_loss_price,
        color: "#F97316",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "SL",
      });
    }

    const markers: any[] = [];
    if (forecast.signal.signal === "long") {
      markers.push({
        time: lastTime,
        position: "belowBar",
        color: "#22C55E",
        shape: "arrowUp",
        text: `LONG ${forecast.signal.expected_return_pct.toFixed(2)}%`,
      });
    } else if (forecast.signal.signal === "short") {
      markers.push({
        time: lastTime,
        position: "aboveBar",
        color: "#F97316",
        shape: "arrowDown",
        text: `SHORT ${forecast.signal.expected_return_pct.toFixed(2)}%`,
      });
    }

    backtest?.trades.forEach((trade) => {
      markers.push({
        time: isoToChartTime(trade.entry_time),
        position: trade.side === "long" ? "belowBar" : "aboveBar",
        color: trade.side === "long" ? "#22C55E" : "#F97316",
        shape: trade.side === "long" ? "arrowUp" : "arrowDown",
        text: trade.side.toUpperCase(),
      });
      markers.push({
        time: isoToChartTime(trade.exit_time),
        position: trade.net_pnl >= 0 ? "aboveBar" : "belowBar",
        color: trade.net_pnl >= 0 ? "#22C55E" : "#F97316",
        shape: "circle",
        text: `${money(trade.net_pnl)} ${trade.exit_reason}`,
      });
    });
    candleSeries.setMarkers(markers.sort((a, b) => Number(a.time) - Number(b.time)));

    chart.subscribeCrosshairMove((param) => {
      const tooltip = tooltipRef.current;
      if (!tooltip || !param.point || !param.time || !chartRef.current) {
        if (tooltip) tooltip.style.display = "none";
        return;
      }

      const bounds = chartRef.current.getBoundingClientRect();
      if (param.point.x < 0 || param.point.y < 0 || param.point.x > bounds.width || param.point.y > bounds.height) {
        tooltip.style.display = "none";
        return;
      }

      const candle = param.seriesData.get(candleSeries) as { close?: number } | undefined;
      const predicted = param.seriesData.get(forecastSeries) as { value?: number } | undefined;
      const close = candle?.close;
      const value = predicted?.value;
      tooltip.innerHTML = `
        <div class="font-medium text-text">${String(param.time)}</div>
        ${close ? `<div>Close: ${money(close)}</div>` : ""}
        ${value ? `<div>Forecast: ${money(value)}</div>` : ""}
        <div>Signal: ${forecast.signal.signal.toUpperCase()}</div>
        <div>Expected: ${forecast.signal.expected_return_pct.toFixed(2)}%</div>
      `;
      tooltip.style.display = "block";
      tooltip.style.left = `${Math.min(param.point.x + 16, bounds.width - 180)}px`;
      tooltip.style.top = `${Math.max(param.point.y - 70, 10)}px`;
    });

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [forecast, backtest]);

  return (
    <section className="relative min-h-[520px] rounded-lg border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-text">BTC Price Forecast</div>
          <div className="text-xs text-muted">
            {forecast ? `${forecast.request.exchange} ${forecast.request.symbol} ${forecast.request.timeframe}` : "Awaiting data"}
          </div>
        </div>
        {forecast?.warnings.length ? <div className="text-xs text-negative">{forecast.warnings[0]}</div> : null}
      </div>
      {forecast ? (
        <>
          <div ref={chartRef} className="h-[520px] w-full" />
          <div
            ref={tooltipRef}
            className="pointer-events-none absolute z-10 hidden min-w-44 rounded-md border border-line bg-ink/95 px-3 py-2 text-xs leading-5 text-muted shadow-glow"
          />
        </>
      ) : (
        <div className="flex h-[520px] items-center justify-center text-sm text-muted">
          Run a forecast to render candles, TimesFM projection, uncertainty bounds, and mock trade markers.
        </div>
      )}
    </section>
  );
}

