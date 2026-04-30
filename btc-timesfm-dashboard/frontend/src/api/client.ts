import type { BacktestRequest, BacktestResponse, ForecastRequest, ForecastResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      message = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? payload);
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function runForecast(payload: ForecastRequest): Promise<ForecastResponse> {
  return requestJson<ForecastResponse>("/forecast", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runBacktest(payload: BacktestRequest): Promise<BacktestResponse> {
  return requestJson<BacktestResponse>("/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSample(): Promise<ForecastResponse> {
  return requestJson<ForecastResponse>("/sample");
}

