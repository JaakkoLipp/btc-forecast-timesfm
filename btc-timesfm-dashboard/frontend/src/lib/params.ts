import type { BacktestRequest } from "../types";

// BacktestRequest is a flat object of primitives (and one nullable). Comparing
// the JSON encoding is sufficient for stale-result detection and avoids
// pulling in a deep-equal dependency.
export function paramsEqual(a: BacktestRequest, b: BacktestRequest): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
