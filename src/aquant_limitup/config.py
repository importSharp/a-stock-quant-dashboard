from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class DataConfig:
    database: Path
    history_start: str
    request_timeout_seconds: int
    request_retries: int
    sync_workers: int


@dataclass(frozen=True)
class UniverseConfig:
    main_board_only: bool
    exclude_st: bool
    min_listing_days: int
    max_price: float | None
    min_average_amount_20: float


@dataclass(frozen=True)
class StrategyConfig:
    top_n: int
    sector_top_n: int
    sector_candidate_top_n: int
    min_sector_members: int
    sector_weight: float
    momentum_20_weight: float
    momentum_60_weight: float
    relative_strength_weight: float
    volume_weight: float
    breakout_weight: float
    trend_quality_weight: float


@dataclass(frozen=True)
class AppConfig:
    data: DataConfig
    universe: UniverseConfig
    strategy: StrategyConfig
    report_directory: Path


def load_config(path: str | Path = "config/default.toml") -> AppConfig:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    data = raw["data"]
    universe = raw["universe"]
    strategy = raw["strategy"]
    return AppConfig(
        data=DataConfig(
            database=Path(data["database"]),
            history_start=data["history_start"],
            request_timeout_seconds=int(data["request_timeout_seconds"]),
            request_retries=int(data["request_retries"]),
            sync_workers=int(data["sync_workers"]),
        ),
        universe=UniverseConfig(
            main_board_only=bool(universe["main_board_only"]),
            exclude_st=bool(universe["exclude_st"]),
            min_listing_days=int(universe["min_listing_days"]),
            max_price=(
                None if universe.get("max_price") is None else float(universe["max_price"])
            ),
            min_average_amount_20=float(universe["min_average_amount_20"]),
        ),
        strategy=StrategyConfig(**strategy),
        report_directory=Path(raw["report"]["directory"]),
    )
