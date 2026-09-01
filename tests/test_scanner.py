import unittest
from dataclasses import replace

import numpy as np
import pandas as pd

from aquant_limitup.config import load_config
from aquant_limitup.features import build_feature_panel
from aquant_limitup.scanner import scan


class ScannerTests(unittest.TestCase):
    def test_scanner_ranks_stronger_stock(self):
        dates = pd.bdate_range("2025-01-01", periods=90)
        bars = []
        stocks = []
        for index, code in enumerate(["000001", "000002", "600001", "600002"]):
            growth = 1.003 + index * 0.001
            prices = 10 * np.power(growth, np.arange(len(dates)))
            for i, (trade_date, close) in enumerate(zip(dates, prices, strict=True)):
                bars.append(
                    {
                        "code": code,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "open": close * 0.995,
                        "close": close,
                        "high": close * 1.01,
                        "low": close * 0.99,
                        "volume": 10_000_000,
                        "amount": 100_000_000 * (1 + i / 500),
                        "amplitude": 2.0,
                        "pct_change": 0.3,
                        "change": 0.03,
                        "turnover": 5.0,
                    }
                )
            stocks.append(
                {
                    "code": code,
                    "name": f"测试{index}",
                    "industry": "测试科技A" if index < 2 else "测试科技B",
                    "list_date": "20200101",
                    "is_st": 0,
                    "market_cap": 10_000_000_000,
                    "float_market_cap": 8_000_000_000,
                    "pe_ttm": 30,
                }
            )
        config = load_config()
        universe = replace(config.universe, min_average_amount_20=1, max_price=35)
        strategy = replace(
            config.strategy,
            min_sector_members=2,
            top_n=4,
            sector_top_n=2,
            sector_candidate_top_n=2,
        )
        panel = build_feature_panel(pd.DataFrame(bars), pd.DataFrame(stocks))
        result = scan(panel, universe, strategy)
        self.assertEqual(result.candidates.iloc[0]["code"], "600002")
        self.assertEqual(len(result.candidates), 4)
        self.assertEqual(len(result.sector_candidates), 4)
        self.assertEqual(
            result.sector_candidates.groupby("industry").size().tolist(), [2, 2]
        )
        self.assertEqual(
            result.sector_candidates.groupby("industry")["sector_rank"]
            .apply(list)
            .tolist(),
            [[1, 2], [1, 2]],
        )
        self.assertEqual(result.sector_candidates.iloc[0]["code"], "600002")
        self.assertEqual(len(result.stock_pool), 4)
        self.assertTrue(result.stock_pool["eligible"].all())
        for sector in result.sectors["industry"]:
            group = result.sector_candidates.loc[
                result.sector_candidates["industry"] == sector
            ]
            self.assertTrue(group["industry"].eq(sector).all())


if __name__ == "__main__":
    unittest.main()
