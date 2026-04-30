from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.schemas import ForecastQuantile, ForecastResult, TargetMode
from app.settings import Settings

INSTALL_HINT = (
    "TimesFM is not installed. Install the current Google Research repository with:\n"
    "git clone https://github.com/google-research/timesfm.git\n"
    "cd timesfm\n"
    "uv pip install -e .[torch]"
)


@dataclass
class ForecastComputation:
    result: ForecastResult
    warnings: list[str] = field(default_factory=list)


def close_to_log_returns(close_prices: np.ndarray | list[float]) -> np.ndarray:
    closes = np.asarray(close_prices, dtype=np.float64)
    if closes.ndim != 1 or closes.size < 2:
        raise ValueError("At least two close prices are required for log-return forecasting.")
    if np.any(closes <= 0):
        raise ValueError("Close prices must be positive to calculate log returns.")
    return np.diff(np.log(closes))


def reconstruct_prices_from_log_returns(
    last_price: float,
    predicted_returns: np.ndarray | list[float],
) -> np.ndarray:
    if last_price <= 0:
        raise ValueError("last_price must be positive.")
    returns = np.asarray(predicted_returns, dtype=np.float64)
    return float(last_price) * np.exp(np.cumsum(returns))


def _safe_float_list(values: np.ndarray | list[float]) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=np.float64).tolist()]


class TimesFMForecaster:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._loaded = False
        self._compiled_infer_is_positive: bool | None = None

    @property
    def model_loaded(self) -> bool:
        return self._loaded

    def _load_model(self, infer_is_positive: bool):
        if self.settings.DEV_FAKE_FORECAST:
            return None

        try:
            import timesfm
            import torch
        except ImportError as exc:
            raise RuntimeError(INSTALL_HINT) from exc

        if self.settings.INFERENCE_DEVICE == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "INFERENCE_DEVICE is set to 'cuda', but CUDA is not available. "
                "Set INFERENCE_DEVICE=cpu for CPU-only local testing."
            )

        torch.set_float32_matmul_precision("high")

        if self._model is None:
            self._model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self.settings.MODEL_CHECKPOINT)
            self._loaded = True

        if self._compiled_infer_is_positive != infer_is_positive:
            self._model.compile(
                timesfm.ForecastConfig(
                    max_context=self.settings.MODEL_MAX_CONTEXT,
                    max_horizon=self.settings.MODEL_MAX_HORIZON,
                    normalize_inputs=True,
                    use_continuous_quantile_head=self.settings.USE_QUANTILES,
                    force_flip_invariance=True,
                    infer_is_positive=infer_is_positive,
                    fix_quantile_crossing=True,
                )
            )
            self._compiled_infer_is_positive = infer_is_positive

        return self._model

    def forecast(
        self,
        close_prices: np.ndarray | list[float],
        horizon: int,
        target_mode: TargetMode,
        use_quantiles: bool = True,
    ) -> ForecastComputation:
        closes = np.asarray(close_prices, dtype=np.float64)
        if closes.ndim != 1 or closes.size < 2:
            raise ValueError("Forecasting requires at least two close prices.")
        if horizon < 1:
            raise ValueError("horizon must be at least 1.")
        if horizon > self.settings.MODEL_MAX_HORIZON:
            raise ValueError(f"horizon exceeds MODEL_MAX_HORIZON={self.settings.MODEL_MAX_HORIZON}.")
        if closes.size > self.settings.MODEL_MAX_CONTEXT:
            raise ValueError(f"lookback exceeds MODEL_MAX_CONTEXT={self.settings.MODEL_MAX_CONTEXT}.")

        warnings: list[str] = []
        last_price = float(closes[-1])

        if target_mode == "log_return":
            model_input = close_to_log_returns(closes)
            infer_is_positive = False
        else:
            model_input = closes
            infer_is_positive = True

        if self.settings.DEV_FAKE_FORECAST:
            result = self._fake_forecast(closes, horizon, target_mode, use_quantiles)
            warnings.append("DEV_FAKE_FORECAST=true: using deterministic naive forecast instead of TimesFM.")
            return ForecastComputation(result=result, warnings=warnings)

        model = self._load_model(infer_is_positive=infer_is_positive)
        point_forecast, quantile_forecast = model.forecast(
            horizon=horizon,
            inputs=[model_input.astype(np.float64)],
        )

        point_values = np.asarray(point_forecast[0], dtype=np.float64)
        if target_mode == "log_return":
            predicted_prices = reconstruct_prices_from_log_returns(last_price, point_values)
            predicted_target_values = point_values
        else:
            predicted_prices = np.maximum(point_values, 0)
            predicted_target_values = predicted_prices

        quantiles = None
        if use_quantiles and quantile_forecast is not None:
            quantiles = self._build_quantiles(
                quantile_forecast=np.asarray(quantile_forecast[0], dtype=np.float64),
                last_price=last_price,
                target_mode=target_mode,
            )

        return ForecastComputation(
            result=ForecastResult(
                predicted_prices=_safe_float_list(predicted_prices),
                predicted_target_values=_safe_float_list(predicted_target_values),
                quantiles=quantiles,
                last_price=last_price,
                target_mode=target_mode,
            ),
            warnings=warnings,
        )

    def _fake_forecast(
        self,
        closes: np.ndarray,
        horizon: int,
        target_mode: TargetMode,
        use_quantiles: bool,
    ) -> ForecastResult:
        last_price = float(closes[-1])
        returns = close_to_log_returns(closes)
        recent = returns[-min(48, returns.size) :]
        drift = float(np.clip(np.nanmean(recent), -0.003, 0.003))
        volatility = float(np.nanstd(recent) or 0.001)

        predicted_returns = np.array([drift * (0.94**idx) for idx in range(horizon)], dtype=np.float64)
        predicted_prices = reconstruct_prices_from_log_returns(last_price, predicted_returns)

        if target_mode == "close":
            predicted_target_values = predicted_prices
        else:
            predicted_target_values = predicted_returns

        quantiles = None
        if use_quantiles:
            lower_returns = predicted_returns - 1.2816 * volatility * np.sqrt(np.arange(1, horizon + 1))
            upper_returns = predicted_returns + 1.2816 * volatility * np.sqrt(np.arange(1, horizon + 1))
            lower_prices = reconstruct_prices_from_log_returns(last_price, lower_returns)
            upper_prices = reconstruct_prices_from_log_returns(last_price, upper_returns)
            quantiles = [
                ForecastQuantile(
                    horizon_index=index,
                    lower=float(min(lower_prices[index], upper_prices[index])),
                    median=float(predicted_prices[index]),
                    upper=float(max(lower_prices[index], upper_prices[index])),
                    mean=float(predicted_prices[index]),
                )
                for index in range(horizon)
            ]

        return ForecastResult(
            predicted_prices=_safe_float_list(predicted_prices),
            predicted_target_values=_safe_float_list(predicted_target_values),
            quantiles=quantiles,
            last_price=last_price,
            target_mode=target_mode,
        )

    def _build_quantiles(
        self,
        quantile_forecast: np.ndarray,
        last_price: float,
        target_mode: TargetMode,
    ) -> list[ForecastQuantile]:
        if quantile_forecast.ndim != 2 or quantile_forecast.shape[0] == 0:
            return []

        width = quantile_forecast.shape[1]
        mean_col = 0
        lower_col = 1 if width > 1 else 0
        median_col = min(5, width - 1)
        upper_col = width - 1

        mean_values = quantile_forecast[:, mean_col]
        lower_values = quantile_forecast[:, lower_col]
        median_values = quantile_forecast[:, median_col]
        upper_values = quantile_forecast[:, upper_col]

        if target_mode == "log_return":
            mean_prices = reconstruct_prices_from_log_returns(last_price, mean_values)
            lower_prices = reconstruct_prices_from_log_returns(last_price, lower_values)
            median_prices = reconstruct_prices_from_log_returns(last_price, median_values)
            upper_prices = reconstruct_prices_from_log_returns(last_price, upper_values)
        else:
            mean_prices = np.maximum(mean_values, 0)
            lower_prices = np.maximum(lower_values, 0)
            median_prices = np.maximum(median_values, 0)
            upper_prices = np.maximum(upper_values, 0)

        quantiles: list[ForecastQuantile] = []
        for index in range(quantile_forecast.shape[0]):
            lower = float(min(lower_prices[index], upper_prices[index]))
            upper = float(max(lower_prices[index], upper_prices[index]))
            quantiles.append(
                ForecastQuantile(
                    horizon_index=index,
                    lower=lower,
                    median=float(median_prices[index]),
                    upper=upper,
                    mean=float(mean_prices[index]) if math.isfinite(float(mean_prices[index])) else None,
                )
            )
        return quantiles
