import { useEffect, useRef } from "react";
import {
  ColorType,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts";
import type { BacktestResponse } from "../types";

interface EquityCurveProps {
  backtest: BacktestResponse;
  initialEquity: number;
}

function money(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function EquityCurve({ backtest, initialEquity }: EquityCurveProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (backtest.equity_curve.length <= 1) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94A3B8",
        fontFamily: "Inter, ui-sans-serif, system-ui",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(31, 41, 55, 0.35)" },
        horzLines: { color: "rgba(31, 41, 55, 0.35)" },
      },
      rightPriceScale: { borderColor: "#1F2937" },
      timeScale: { borderColor: "#1F2937", timeVisible: true },
    });

    const equitySeries = chart.addAreaSeries({
      lineColor: "#22D3EE",
      topColor: "rgba(34, 211, 238, 0.20)",
      bottomColor: "rgba(34, 211, 238, 0.00)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    equitySeries.setData(
      backtest.equity_curve.map((point) => ({
        time: Math.floor(point.timestamp / 1000) as UTCTimestamp,
        value: point.equity,
      })),
    );

    const first = backtest.equity_curve[0];
    const last = backtest.equity_curve[backtest.equity_curve.length - 1];
    if (first && last) {
      const baselineSeries = chart.addLineSeries({
        color: "#94A3B8",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      baselineSeries.setData([
        {
          time: Math.floor(first.timestamp / 1000) as UTCTimestamp,
          value: initialEquity,
        },
        {
          time: Math.floor(last.timestamp / 1000) as UTCTimestamp,
          value: initialEquity + backtest.baseline.buy_and_hold_pnl,
        },
      ]);
    }

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [backtest, initialEquity]);

  if (backtest.equity_curve.length <= 1) {
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-line bg-mutedPanel/40 text-xs text-muted">
        Not enough trades to plot an equity curve.
      </div>
    );
  }

  const finalEquity = backtest.metrics.final_equity;
  const buyHoldEquity = initialEquity + backtest.baseline.buy_and_hold_pnl;

  return (
    <div className="rounded-lg border border-line bg-panel">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-3 py-2 text-xs">
        <span className="font-semibold text-text">Equity curve</span>
        <span className="flex items-center gap-1.5 text-muted">
          <span className="inline-block h-2 w-3 rounded-sm bg-accent" />
          Strategy {money(finalEquity)}
        </span>
        <span className="flex items-center gap-1.5 text-muted">
          <span className="inline-block h-0 w-3 border-t border-dashed border-muted" />
          Buy &amp; hold {money(buyHoldEquity)}
        </span>
      </div>
      <div ref={containerRef} className="h-44 w-full" />
    </div>
  );
}
