from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import UniverseConfig, StrategyConfig


@dataclass(frozen=True)
class ScanResult:
    as_of: str
    universe_size: int
    candidates: pd.DataFrame
    sectors: pd.DataFrame
    sector_candidates: pd.DataFrame
    stock_pool: pd.DataFrame


def scan(
    panel: pd.DataFrame,
    universe: UniverseConfig,
    strategy: StrategyConfig,
    *,
    as_of: str | None = None,
) -> ScanResult:
    if panel.empty:
        raise ValueError("没有足够行情数据，请先运行 sync")
    target_date = pd.Timestamp(as_of) if as_of else panel["trade_date"].max()
    base_day = panel.loc[panel["trade_date"] == target_date].copy()
    base_day = base_day.dropna(
        subset=["return_20", "return_60", "sector_score", "amount_ratio"]
    )
    analysis_day = _score_day(base_day, strategy)
    day = _apply_universe(base_day, universe, target_date)
    day = day.loc[day["sector_members"] >= strategy.min_sector_members].copy()
    if day.empty:
        raise ValueError("筛选后股票池为空；可降低成交额门槛或同步更多股票")
    day = _score_day(day, strategy)

    candidate_columns = [
        "code", "name", "industry", "close", "pct_change", "strategy_type",
        "model_score", "sector_score", "return_20", "return_60", "amount_ratio",
        "average_turnover_5", "breakout_20", "reason",
    ]
    candidates = day[candidate_columns].head(strategy.top_n).reset_index(drop=True)
    sector_columns = [
        "industry", "sector_score", "sector_members", "sector_return_5",
        "sector_return_20", "sector_breadth_20", "sector_amount_ratio",
        "sector_touch_rate", "sector_close_rate",
    ]
    sectors = (
        day[sector_columns]
        .drop_duplicates("industry")
        .sort_values("sector_score", ascending=False)
        .head(strategy.sector_top_n)
        .reset_index(drop=True)
    )
    sector_order = {
        industry: rank_no
        for rank_no, industry in enumerate(sectors["industry"].tolist(), start=1)
    }
    sector_candidates = day.loc[day["industry"].isin(sector_order)].copy()
    sector_candidates["sector_rank"] = (
        sector_candidates.groupby("industry", sort=False).cumcount() + 1
    )
    sector_candidates["sector_order"] = sector_candidates["industry"].map(sector_order)
    sector_candidates = (
        sector_candidates.loc[
            sector_candidates["sector_rank"] <= strategy.sector_candidate_top_n,
            candidate_columns + ["sector_rank", "sector_order"],
        ]
        .sort_values(["sector_order", "sector_rank"])
        .drop(columns="sector_order")
        .reset_index(drop=True)
    )
    eligible_codes = set(day["code"])
    day_for_pool = day.copy()
    day_for_pool["eligible"] = True
    day_for_pool["eligibility_reason"] = "符合当前股票池"
    excluded = analysis_day.loc[~analysis_day["code"].isin(eligible_codes)].copy()
    excluded["eligible"] = False
    excluded["eligibility_reason"] = excluded.apply(
        lambda row: _eligibility_reason(row, universe, strategy, target_date), axis=1
    )
    stock_pool = (
        pd.concat([day_for_pool, excluded], ignore_index=True)
        .sort_values(["eligible", "model_score", "amount"], ascending=[False, False, False])
        [candidate_columns + ["eligible", "eligibility_reason"]]
        .reset_index(drop=True)
    )
    return ScanResult(
        as_of=target_date.strftime("%Y-%m-%d"),
        universe_size=len(day),
        candidates=candidates,
        sectors=sectors,
        sector_candidates=sector_candidates,
        stock_pool=stock_pool,
    )


def _score_day(day: pd.DataFrame, strategy: StrategyConfig) -> pd.DataFrame:
    scored = day.copy()
    scored["momentum_20_score"] = _percentile(scored["return_20"])
    scored["momentum_60_score"] = _percentile(scored["return_60"])
    scored["relative_strength_score"] = _percentile(scored["relative_strength_20"])
    scored["volume_score"] = _percentile(scored["amount_ratio"].clip(upper=5))
    scored["breakout_score"] = _percentile(scored["breakout_20"].clip(-0.20, 0.05))
    scored["trend_quality_score"] = (
        1 - ((scored["price_vs_ma20"] - 0.05).abs() / 0.20)
    ).clip(0, 1)
    scored["model_score"] = 100 * (
        strategy.sector_weight * scored["sector_score"]
        + strategy.momentum_20_weight * scored["momentum_20_score"]
        + strategy.momentum_60_weight * scored["momentum_60_score"]
        + strategy.relative_strength_weight * scored["relative_strength_score"]
        + strategy.volume_weight * scored["volume_score"]
        + strategy.breakout_weight * scored["breakout_score"]
        + strategy.trend_quality_weight * scored["trend_quality_score"]
    )
    scored["model_score"] = scored["model_score"].round(2)
    scored["strategy_type"] = np.select(
        [
            scored["closed_limit"] & ~scored["previous_closed_limit"],
            scored["recent_limitups_10"].fillna(0).eq(0),
        ],
        ["1进2观察", "首板观察"],
        default="趋势板观察",
    )
    scored["reason"] = scored.apply(_reason, axis=1)
    return scored.sort_values(["model_score", "amount"], ascending=False)


def _apply_universe(day: pd.DataFrame, config: UniverseConfig, target_date: pd.Timestamp) -> pd.DataFrame:
    filtered = day.copy()
    if config.exclude_st and "is_st" in filtered:
        filtered = filtered.loc[filtered["is_st"].fillna(0).eq(0)]
    if config.max_price is not None:
        filtered = filtered.loc[filtered["close"] <= config.max_price]
    filtered = filtered.loc[
        filtered["average_amount_20"] >= config.min_average_amount_20
    ]
    if "list_date" in filtered:
        listing = pd.to_datetime(filtered["list_date"], format="%Y%m%d", errors="coerce")
        filtered = filtered.loc[
            listing.isna() | ((target_date - listing).dt.days >= config.min_listing_days)
        ]
    return filtered.dropna(
        subset=["return_20", "return_60", "sector_score", "amount_ratio"]
    )


def _percentile(series: pd.Series) -> pd.Series:
    return series.rank(pct=True).fillna(0)


def _eligibility_reason(
    row: pd.Series,
    universe: UniverseConfig,
    strategy: StrategyConfig,
    target_date: pd.Timestamp,
) -> str:
    reasons = []
    if universe.exclude_st and bool(row.get("is_st", 0)):
        reasons.append("ST股票已排除")
    if universe.max_price is not None and row["close"] > universe.max_price:
        reasons.append(f"股价高于{universe.max_price:g}元")
    if row["average_amount_20"] < universe.min_average_amount_20:
        reasons.append("20日平均成交额不足")
    list_date = pd.to_datetime(str(row.get("list_date", "")), format="%Y%m%d", errors="coerce")
    if pd.notna(list_date) and (target_date - list_date).days < universe.min_listing_days:
        reasons.append("上市时间不足")
    if row["sector_members"] < strategy.min_sector_members:
        reasons.append("所属行业样本数量不足")
    return "、".join(reasons) or "未通过当前股票池规则"


def _reason(row: pd.Series) -> str:
    reasons = []
    if row["sector_score"] >= 0.70:
        reasons.append("板块强")
    if row["return_20"] > 0.08:
        reasons.append("20日趋势强")
    if row["relative_strength_20"] > 0.03:
        reasons.append("强于板块")
    if 1.2 <= row["amount_ratio"] <= 3.5:
        reasons.append("成交额放大")
    if row["breakout_20"] >= -0.02:
        reasons.append("接近20日突破")
    if row["price_vs_ma20"] > 0.20:
        reasons.append("高位过热")
    return "、".join(reasons) or "综合评分入选"
