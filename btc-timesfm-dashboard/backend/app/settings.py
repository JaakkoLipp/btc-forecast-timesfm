import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_NAME: str = "BTC TimesFM Dashboard"
    CORS_ORIGINS: list[str] | str = Field(default_factory=lambda: ["http://localhost:5173"])
    DEFAULT_EXCHANGE: str = "binance"
    DEFAULT_SYMBOL: str = "BTC/USDT"
    DEFAULT_TIMEFRAME: str = "5m"
    DEFAULT_LOOKBACK: int = 1024
    DEFAULT_HORIZON: int = 24
    MAX_LOOKBACK: int = 16000
    MAX_HORIZON: int = 1000
    MODEL_CHECKPOINT: str = "google/timesfm-2.5-200m-pytorch"
    MODEL_MAX_CONTEXT: int = 2048
    MODEL_MAX_HORIZON: int = 256
    USE_QUANTILES: bool = True
    SQLITE_PATH: str = "./btc_timesfm.db"
    DEV_FAKE_FORECAST: bool = False
    INFERENCE_DEVICE: Literal["cpu", "cuda"] = "cpu"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
