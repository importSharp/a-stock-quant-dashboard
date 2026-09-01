from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import UniverseConfig, StrategyConfig
from .scanner import scan


@dataclass(frozen=True)
class BacktestSummary:
    start: str
    end: str
    days: int
    top_k: int
    touch_precision: float
    close_limit_precision: float
    average_next_return: float
    observations: int


def walk_forward_backtest(
    panel: pd.DataFrame,
    universe: UniverseConfig,
    strategy: StrategyConfig,
    *,
    start: str | None = None,
    end: str | None = None,
    top_k: int = 5,
) -> BacktestSummary:
    dates = sorted(panel["trade_date"].dropna().unique())
    if start:
        dates = [d for d in dates if pd.Timestamp(d) >= pd.Timestamp(start)]
    if end:
        dates = [d for d in dates if pd.Timestamp(d) <= pd.Timestamp(end)]

    selected = []
    for trade_date in dates:
        try:
            result = scan(panel, universe, strategy, as_of=str(pd.Timestamp(trade_date).date()))
        except ValueError:
            continue
        top = result.candidates.head(top_k)[["code", "model_score"]].copy()
        labels = panel.loc[
            panel["trade_date"] == pd.Timestamp(trade_date),
            ["code", "next_touch", "next_close_limit", "next_return"],
        ]
        merged = top.merge(labels, on="code", how="left")
        merged["trade_date"] = pd.Timestamp(trade_date)
        selected.append(merged)

    if not selected:
        raise ValueError("没有可回测的交易日")
    observations = pd.concat(selected, ignore_index=True).dropna(subset=["next_touch"])
    return BacktestSummary(
        start=observations["trade_date"].min().strftime("%Y-%m-%d"),
        end=observations["trade_date"].max().strftime("%Y-%m-%d"),
        days=observations["trade_date"].nunique(),
        top_k=top_k,
        touch_precision=float(observations["next_touch"].astype(float).mean()),
        close_limit_precision=float(observations["next_close_limit"].astype(float).mean()),
        average_next_return=float(observations["next_return"].mean()),
        observations=len(observations),
    )

