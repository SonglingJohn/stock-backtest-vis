from __future__ import annotations

from typing import Any

from backend.backtest import BacktestRequest, StockRequest, run_backtest
from backend.data_source import (
    load_a_share_names,
    load_a_share_prices,
    load_index_prices,
    load_market_indexes,
    load_stock_info,
    market_index_names,
    resolve_stock_query,
)


def health() -> dict[str, Any]:
    return {"ok": True}


def get_stock_info(symbol: str) -> dict[str, Any]:
    return load_stock_info(symbol)


def resolve_stock(query: str) -> dict[str, Any]:
    return resolve_stock_query(query)


def get_market_indexes() -> dict[str, Any]:
    return {"indexes": load_market_indexes()}


def preload_stock(symbol: str, start_year: int, end_year: int) -> dict[str, Any]:
    rows = load_a_share_prices(symbol, start_year, end_year)
    return {
        "symbol": symbol,
        "start_year": start_year,
        "end_year": end_year,
        "rows": len(rows),
        "first_date": rows[0]["date"] if rows else None,
        "last_date": rows[-1]["date"] if rows else None,
    }


def run_backtest_api(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_backtest_request(payload)
    prices_by_symbol = {
        stock.symbol: load_a_share_prices(stock.symbol, request.start_year, request.end_year)
        for stock in request.stocks
    }
    prices_by_symbol.update(
        {
            symbol: load_index_prices(symbol, request.start_year, request.end_year)
            for symbol in request.benchmarks
        }
    )
    result = run_backtest(request, prices_by_symbol)
    names = load_a_share_names()
    names.update(market_index_names())
    for item in result["series"]:
        item["name"] = item.get("name") or names.get(item["symbol"], item["symbol"])
        for component in item.get("components", []):
            component["name"] = names.get(component["symbol"], component["symbol"])
    return result


def parse_backtest_request(payload: dict[str, Any]) -> BacktestRequest:
    stocks = [
        StockRequest(
            symbol=resolve_stock_query(str(item.get("symbol", "")).strip())["symbol"],
            percent=_optional_float(item.get("percent")),
        )
        for item in payload.get("stocks", [])
        if str(item.get("symbol", "")).strip()
    ]
    return BacktestRequest(
        stocks=stocks,
        buy_method=str(payload.get("buyMethod", "lump_sum")),
        amount=float(payload.get("amount", 0)),
        start_year=int(payload.get("startYear", 0)),
        end_year=int(payload.get("endYear", 0)),
        benchmarks=[str(item).strip() for item in payload.get("benchmarks", []) if str(item).strip()],
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(str(value).replace("%", ""))
