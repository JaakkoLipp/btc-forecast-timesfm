import { ShieldAlert } from "lucide-react";

export function Disclaimer() {
  return (
    <details className="rounded-lg border border-line bg-panel px-4 py-3 text-xs leading-5 text-muted [&[open]_summary]:mb-2">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-text">
        <ShieldAlert size={15} className="text-accent" />
        Research only — read more
      </summary>
      This dashboard is for research and paper trading only. It does not provide financial advice and does not
      execute real trades. Forecasts and mock backtests can be wrong and may not reflect real execution,
      liquidity, fees, slippage, or market risk.
    </details>
  );
}
