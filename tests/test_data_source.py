import json
import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.data_source import (
    FALLBACK_MARKET_INDEXES,
    _fetch_akshare_prices,
    load_a_share_prices,
    load_market_indexes,
    resolve_stock_query,
)


class DataSourceCacheTest(unittest.TestCase):
    def test_reuses_covering_cache_before_requesting_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "600519-2000-2026-hfq.json"
            cache_file.write_text(
                json.dumps(
                    [
                        {"date": "2011-12-30", "close": 10.0},
                        {"date": "2012-01-04", "close": 11.0},
                        {"date": "2026-01-05", "close": 20.0},
                    ]
                ),
                encoding="utf-8",
            )

            with patch("backend.data_source._fetch_akshare_prices") as fetch:
                fetch.side_effect = AssertionError("network should not be called")
                rows = load_a_share_prices("600519", 2012, 2026, cache_dir=cache_dir)

            self.assertEqual(
                rows,
                [
                    {"date": "2012-01-04", "close": 11.0},
                    {"date": "2026-01-05", "close": 20.0},
                ],
            )

    def test_uses_hfq_cache_key_for_long_term_return_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "600519-2000-2026-hfq.json"
            cache_file.write_text(
                json.dumps([{"date": "2001-08-27", "close": 35.55}]),
                encoding="utf-8",
            )

            rows = load_a_share_prices("600519", 2000, 2026, cache_dir=cache_dir)

            self.assertEqual(rows[0]["date"], "2001-08-27")

    def test_falls_back_to_legacy_qfq_cache_and_rebases_non_positive_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "600519-2000-2026-qfq.json"
            cache_file.write_text(
                json.dumps(
                    [
                        {"date": "2001-08-27", "close": -284.45},
                        {"date": "2001-08-28", "close": -284.18},
                        {"date": "2026-01-05", "close": 1550.0},
                    ]
                ),
                encoding="utf-8",
            )

            with patch("backend.data_source._fetch_akshare_prices") as fetch:
                fetch.side_effect = AssertionError("network should not be called")
                rows = load_a_share_prices("600519", 2000, 2026, cache_dir=cache_dir)

            self.assertEqual(rows[0]["date"], "2001-08-27")
            self.assertGreater(rows[0]["close"], 0)
            self.assertGreater(rows[-1]["close"], rows[0]["close"])

    def test_market_indexes_use_fallback_when_network_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "market-indexes.json"

            with patch("backend.data_source._fetch_market_indexes") as fetch:
                fetch.side_effect = RuntimeError("network unavailable")
                rows = load_market_indexes(cache_file=cache_file)

            self.assertEqual(rows, FALLBACK_MARKET_INDEXES)
            self.assertEqual(
                [item["name"] for item in rows],
                ["上证指数", "深证成指", "创业板", "沪深300", "科创50", "北证50"],
            )

    def test_stock_price_fetch_falls_back_to_sina_when_eastmoney_fails(self):
        fake_akshare = types.SimpleNamespace(
            stock_zh_a_hist=lambda **_: (_ for _ in ()).throw(RuntimeError("eastmoney unavailable")),
            stock_zh_a_daily=lambda **_: pd.DataFrame(
                [
                    {"date": "2024-01-02", "close": 520.05},
                    {"date": "2024-01-03", "close": 535.25},
                ]
            ),
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            rows = _fetch_akshare_prices("300308", 2024, 2026)

        self.assertEqual(rows[0], {"date": "2024-01-02", "close": 520.05})
        self.assertEqual(rows[-1], {"date": "2024-01-03", "close": 535.25})

    def test_resolves_stock_by_code_or_chinese_name(self):
        names = {"300308": "中际旭创", "600522": "中天科技"}

        self.assertEqual(resolve_stock_query("300308", names), {"symbol": "300308", "name": "中际旭创"})
        self.assertEqual(resolve_stock_query("中际旭创", names), {"symbol": "300308", "name": "中际旭创"})
        self.assertEqual(resolve_stock_query("旭创", names), {"symbol": "300308", "name": "中际旭创"})


if __name__ == "__main__":
    unittest.main()
