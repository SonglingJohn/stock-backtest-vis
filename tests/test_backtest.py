import unittest

from backend.backtest import BacktestRequest, StockRequest, run_backtest


class BacktestEngineTest(unittest.TestCase):
    def test_lump_sum_buys_on_first_trading_day_and_reports_final_profit(self):
        prices_by_symbol = {
            "600519": [
                {"date": "2019-01-02", "close": 10.0},
                {"date": "2019-12-31", "close": 12.0},
                {"date": "2020-01-02", "close": 15.0},
            ]
        }
        request = BacktestRequest(
            stocks=[StockRequest(symbol="600519", percent=None)],
            buy_method="lump_sum",
            amount=1000.0,
            start_year=2019,
            end_year=2020,
        )

        result = run_backtest(request, prices_by_symbol)

        series = result["series"][0]
        self.assertEqual(series["symbol"], "600519")
        self.assertEqual(series["snapshots"][-1]["date"], "2020-01-02")
        self.assertAlmostEqual(series["summary"]["total_invested"], 1000.0)
        self.assertAlmostEqual(series["summary"]["final_value"], 1500.0)
        self.assertAlmostEqual(series["summary"]["profit"], 500.0)
        self.assertAlmostEqual(series["summary"]["return_rate"], 0.5)

    def test_annual_fixed_investment_buys_first_trading_day_each_year(self):
        prices_by_symbol = {
            "601318": [
                {"date": "2019-01-03", "close": 10.0},
                {"date": "2019-12-31", "close": 11.0},
                {"date": "2020-01-02", "close": 20.0},
                {"date": "2020-12-31", "close": 30.0},
            ]
        }
        request = BacktestRequest(
            stocks=[StockRequest(symbol="601318", percent=100.0)],
            buy_method="annual",
            amount=1000.0,
            start_year=2019,
            end_year=2020,
        )

        result = run_backtest(request, prices_by_symbol)

        summary = result["series"][0]["summary"]
        self.assertAlmostEqual(summary["total_invested"], 2000.0)
        self.assertAlmostEqual(summary["final_value"], 4500.0)
        self.assertAlmostEqual(summary["profit"], 2500.0)
        self.assertAlmostEqual(summary["return_rate"], 1.25)

    def test_multiple_stocks_are_combined_into_user_configuration_series(self):
        prices_by_symbol = {
            "600519": [
                {"date": "2020-01-02", "close": 10.0},
                {"date": "2020-12-31", "close": 20.0},
            ],
            "601318": [
                {"date": "2020-01-02", "close": 50.0},
                {"date": "2020-12-31", "close": 25.0},
            ],
        }
        request = BacktestRequest(
            stocks=[
                StockRequest(symbol="600519", percent=50.0),
                StockRequest(symbol="601318", percent=50.0),
            ],
            buy_method="lump_sum",
            amount=1000.0,
            start_year=2020,
            end_year=2020,
        )

        result = run_backtest(request, prices_by_symbol)

        self.assertEqual([item["symbol"] for item in result["series"]], ["USER_CONFIG"])
        self.assertEqual(result["series"][0]["name"], "用户配置")
        self.assertEqual(result["series"][0]["components"][0]["symbol"], "600519")
        self.assertAlmostEqual(result["series"][0]["components"][0]["allocation"], 0.5)
        self.assertEqual(result["series"][0]["components"][1]["symbol"], "601318")
        self.assertAlmostEqual(result["series"][0]["components"][1]["allocation"], 0.5)
        self.assertEqual(result["series"][0]["snapshots"][-1]["date"], "2020-12-31")
        self.assertAlmostEqual(result["series"][0]["summary"]["total_invested"], 1000.0)
        self.assertAlmostEqual(result["series"][0]["summary"]["final_value"], 1250.0)
        self.assertAlmostEqual(result["series"][0]["summary"]["profit"], 250.0)
        self.assertAlmostEqual(result["series"][0]["summary"]["return_rate"], 0.25)

    def test_index_benchmarks_do_not_change_stock_allocations(self):
        prices_by_symbol = {
            "600519": [
                {"date": "2020-01-02", "close": 10.0},
                {"date": "2020-12-31", "close": 20.0},
            ],
            "601318": [
                {"date": "2020-01-02", "close": 50.0},
                {"date": "2020-12-31", "close": 25.0},
            ],
            "000001": [
                {"date": "2020-01-02", "close": 100.0},
                {"date": "2020-12-31", "close": 150.0},
            ],
        }
        request = BacktestRequest(
            stocks=[
                StockRequest(symbol="600519", percent=50.0),
                StockRequest(symbol="601318", percent=50.0),
            ],
            buy_method="lump_sum",
            amount=1000,
            start_year=2020,
            end_year=2020,
            benchmarks=["000001"],
        )

        result = run_backtest(request, prices_by_symbol)

        self.assertEqual([item["symbol"] for item in result["series"]], ["USER_CONFIG", "000001"])
        self.assertFalse(result["series"][0]["benchmark"])
        self.assertTrue(result["series"][1]["benchmark"])
        self.assertAlmostEqual(result["series"][0]["summary"]["total_invested"], 1000.0)
        self.assertAlmostEqual(result["series"][0]["summary"]["final_value"], 1250.0)
        self.assertAlmostEqual(result["series"][1]["summary"]["total_invested"], 1000.0)
        self.assertAlmostEqual(result["series"][1]["summary"]["return_rate"], 0.5)

    def test_invalid_year_range_is_rejected(self):
        request = BacktestRequest(
            stocks=[StockRequest(symbol="600519", percent=None)],
            buy_method="lump_sum",
            amount=1000.0,
            start_year=2021,
            end_year=2020,
        )

        with self.assertRaises(ValueError):
            run_backtest(request, {"600519": []})

    def test_lump_sum_buys_first_available_trading_day_when_start_year_has_no_valid_price(self):
        prices_by_symbol = {
            "600519": [
                {"date": "2018-01-02", "close": 10.0},
                {"date": "2018-12-31", "close": 20.0},
            ]
        }
        request = BacktestRequest(
            stocks=[StockRequest(symbol="600519", percent=100.0)],
            buy_method="lump_sum",
            amount=6000.0,
            start_year=2017,
            end_year=2018,
        )

        result = run_backtest(request, prices_by_symbol)

        summary = result["series"][0]["summary"]
        self.assertAlmostEqual(summary["total_invested"], 6000.0)
        self.assertAlmostEqual(summary["final_value"], 12000.0)
        self.assertEqual(result["series"][0]["snapshots"][0]["date"], "2018-01-02")


if __name__ == "__main__":
    unittest.main()
