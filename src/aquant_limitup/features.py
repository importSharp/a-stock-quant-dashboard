from __future__ import annotations

import numpy as np
import pandas as pd


def build_feature_panel(bars: pd.DataFrame, stocks: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()
    frame = bars.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["code", "trade_date"]).reset_index(drop=True)
    groups = frame.groupby("code", group_keys=False)

    frame["previous_close"] = groups["close"].shift(1)
    frame["return_5"] = groups["close"].pct_change(5, fill_method=None)
    frame["return_20"] = groups["close"].pct_change(20, fill_method=None)
    frame["return_60"] = groups["close"].pct_change(60, fill_method=None)
    frame["ma_20"] = groups["close"].transform(lambda s: s.rolling(20).mean())
    frame["ma_60"] = groups["close"].transform(lambda s: s.rolling(60).mean())
    frame["average_amount_20"] = groups["amount"].transform(lambda s: s.rolling(20).mean())
    previous_amount_average = groups["amount"].transform(
        lambda s: s.shift(1).rolling(20).mean()
    )
    frame["amount_ratio"] = frame["amount"] / previous_amount_average.replace(0, np.nan)
    frame["average_turnover_5"] = groups["turnover"].transform(lambda s: s.rolling(5).mean())
    frame["price_vs_ma20"] = frame["close"] / frame["ma_20"] - 1
    frame["price_vs_ma60"] = frame["close"] / frame["ma_60"] - 1
    previous_high_20 = groups["high"].transform(lambda s: s.shift(1).rolling(20).max())
    frame["breakout_20"] = frame["close"] / previous_high_20 - 1

    # Main-board non-ST approximation. Historical ST status requires a licensed status history.
    raw_limit = frame["previous_close"] * 1.10
    frame["limit_up_price"] = np.floor(raw_limit * 100 + 0.5) / 100
    frame["touched_limit"] = frame["high"] >= frame["limit_up_price"] - 0.001
    frame["closed_limit"] = frame["close"] >= frame["limit_up_price"] - 0.001
    frame["previous_closed_limit"] = groups["closed_limit"].shift(1).fillna(False).astype(bool)
    frame["recent_limitups_10"] = groups["closed_limit"].transform(
        lambda s: s.shift(1).rolling(10).sum()
    )
    frame["next_touch"] = groups["touched_limit"].shift(-1)
    frame["next_close_limit"] = groups["closed_limit"].shift(-1)
    frame["next_return"] = groups["close"].shift(-1) / frame["close"] - 1

    stock_columns = [
        "code", "name", "industry", "list_date", "is_st", "market_cap",
        "float_market_cap", "pe_ttm",
    ]
    available = [column for column in stock_columns if column in stocks.columns]
    frame = frame.merge(stocks[available], on="code", how="left")
    frame["industry"] = frame["industry"].fillna("未分类")
    frame["relative_strength_20"] = frame["return_20"] - frame.groupby(
        ["trade_date", "industry"]
    )["return_20"].transform("median")
    return add_sector_features(frame)


def add_sector_features(frame: pd.DataFrame) -> pd.DataFrame:
    required = frame.dropna(subset=["return_20", "return_60", "ma_20", "amount_ratio"]).copy()
    if required.empty:
        return required
    required["above_ma20"] = required["close"] > required["ma_20"]
    grouped = required.groupby(["trade_date", "industry"], as_index=False).agg(
        sector_members=("code", "nunique"),
        sector_return_5=("return_5", "median"),
        sector_return_20=("return_20", "median"),
        sector_breadth_20=("above_ma20", "mean"),
        sector_amount_ratio=("amount_ratio", "median"),
        sector_touch_rate=("touched_limit", "mean"),
        sector_close_rate=("closed_limit", "mean"),
    )
    metrics = [
        "sector_return_5", "sector_return_20", "sector_breadth_20",
        "sector_amount_ratio", "sector_touch_rate", "sector_close_rate",
    ]
    weights = [0.20, 0.15, 0.20, 0.15, 0.15, 0.15]
    grouped["sector_score"] = 0.0
    for metric, weight in zip(metrics, weights, strict=True):
        percentile = grouped.groupby("trade_date")[metric].rank(pct=True).fillna(0)
        grouped["sector_score"] += percentile * weight
    return required.merge(grouped, on=["trade_date", "industry"], how="left")

