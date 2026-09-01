import unittest
from dataclasses import replace

import numpy as np
import pandas as pd

from aquant_limitup.backtest import walk_forward_backtest
from aquant_limitup.config import load_config
from aquant_limitup.features import build_feature_panel


class BacktestTests(unittest.TestCase):
    def test_walk_forward_does_not_use_last_day_without_label(self):
        dates = pd.bdate_range("2025-01-01", periods=85)
        bars = []
        stocks = []
        for index, code in enumerate(["000001", "000002", "600001"]):
            prices = 10 * np.power(1.002 + index * 0.0005, np.arange(len(dates)))
            for trade_date, close in zip(dates, prices, strict=True):
                bars.append(
                    {
                        "code": code,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "open": close,
                        "close": close,
                        "high": close * 1.01,
                        "low": close * 0.99,
                        "volume": 1_000_000,
                        "amount": 100_000_000,
                        "amplitude": 2.0,
                        "pct_change": 0.2,
                        "change": 0.02,
                        "turnover": 4.0,
                    }
                )
            stocks.append(
                {
                    "code": code,
                    "name": code,
                    "industry": "测试",
                    "list_date": "20200101",
                    "is_st": 0,
                    "market_cap": 10_000_000_000,
                    "float_market_cap": 8_000_000_000,
                    "pe_ttm": 20,
                }
            )
        cfg = load_config()
        universe = replace(cfg.universe, min_average_amount_20=1, max_price=None)
        strategy = replace(cfg.strategy, min_sector_members=3, top_n=3)
        panel = build_feature_panel(pd.DataFrame(bars), pd.DataFrame(stocks))
        summary = walk_forward_backtest(panel, universe, strategy, top_k=2)
        self.assertGreater(summary.days, 0)
        self.assertLess(summary.end, dates[-1].strftime("%Y-%m-%d"))
        self.assertEqual(summary.observations, summary.days * 2)


if __name__ == "__main__":
    unittest.main()
