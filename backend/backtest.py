from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import pow
from typing import Any


@dataclass(frozen=True)
class StockRequest:
    symbol: str
    percent: float | None = None


@dataclass(frozen=True)
class BacktestRequest:
    stocks: list[StockRequest]
    buy_method: str
    amount: float
    start_year: int
    end_year: int
    benchmarks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceRow:
    date: date
    close: float


def run_backtest(request: BacktestRequest, prices_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    _validate_request(request)
    allocations = _allocations(request.stocks)
    series = []
    stock_series = []

    for stock, allocation in zip(request.stocks, allocations):
        rows = _parse_prices(prices_by_symbol.get(stock.symbol, []), request.start_year, request.end_year)
        if not rows:
            raise ValueError(f"No price data for {stock.symbol} in selected range")

        invested_amount = request.amount * allocation
        snapshots = _simulate_series(rows, request.buy_method, invested_amount, request.start_year, request.end_year)
        summary = _summarize(snapshots)
        stock_series.append(
            {
                "symbol": stock.symbol,
                "allocation": allocation,
                "benchmark": False,
                "snapshots": snapshots,
                "summary": summary,
            }
        )

    if len(stock_series) == 1:
        series.extend(stock_series)
    else:
        portfolio_snapshots = _combine_portfolio_snapshots([item["snapshots"] for item in stock_series])
        series.append(
            {
                "symbol": "USER_CONFIG",
                "name": "用户配置",
                "allocation": 1.0,
                "benchmark": False,
                "components": [
                    {
                        "symbol": item["symbol"],
                        "allocation": item["allocation"],
                    }
                    for item in stock_series
                ],
                "snapshots": portfolio_snapshots,
                "summary": _summarize(portfolio_snapshots),
            }
        )

    for symbol in request.benchmarks:
        rows = _parse_prices(prices_by_symbol.get(symbol, []), request.start_year, request.end_year)
        if not rows:
            raise ValueError(f"No price data for {symbol} in selected range")

        snapshots = _simulate_series(rows, request.buy_method, request.amount, request.start_year, request.end_year)
        summary = _summarize(snapshots)
        series.append(
            {
                "symbol": symbol,
                "allocation": 0.0,
                "benchmark": True,
                "snapshots": snapshots,
                "summary": summary,
            }
        )

    return {
        "buy_method": request.buy_method,
        "amount": request.amount,
        "start_year": request.start_year,
        "end_year": request.end_year,
        "series": series,
    }


def _combine_portfolio_snapshots(series_snapshots: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    dates = sorted({snapshot["date"] for snapshots in series_snapshots for snapshot in snapshots})
    positions = [0 for _ in series_snapshots]
    latest: list[dict[str, Any] | None] = [None for _ in series_snapshots]
    peak_value = 0.0
    combined = []

    for current_date in dates:
        for index, snapshots in enumerate(series_snapshots):
            while positions[index] < len(snapshots) and snapshots[positions[index]]["date"] <= current_date:
                latest[index] = snapshots[positions[index]]
                positions[index] += 1

        active = [snapshot for snapshot in latest if snapshot is not None]
        if not active:
            continue

        invested = sum(snapshot["invested"] for snapshot in active)
        value = sum(snapshot["value"] for snapshot in active)
        peak_value = max(peak_value, value)
        drawdown = 0.0 if peak_value == 0 else (value - peak_value) / peak_value
        combined.append(
            {
                "date": current_date,
                "year": _parse_date(current_date).year,
                "close": value,
                "shares": 1.0,
                "invested": invested,
                "value": value,
                "profit": value - invested,
                "return_rate": 0.0 if invested == 0 else (value - invested) / invested,
                "drawdown": drawdown,
            }
        )

    return combined


def _validate_request(request: BacktestRequest) -> None:
    if not request.stocks:
        raise ValueError("At least one stock is required")
    if request.buy_method not in {"lump_sum", "annual"}:
        raise ValueError("buy_method must be lump_sum or annual")
    if request.amount <= 0:
        raise ValueError("amount must be greater than 0")
    if request.start_year > request.end_year:
        raise ValueError("start_year must be before or equal to end_year")


def _allocations(stocks: list[StockRequest]) -> list[float]:
    if len(stocks) == 1 and stocks[0].percent is None:
        return [1.0]

    raw = [100.0 if stock.percent is None else stock.percent for stock in stocks]
    if any(value <= 0 for value in raw):
        raise ValueError("stock percent must be greater than 0")

    total = sum(raw)
    if total <= 0:
        raise ValueError("stock percent total must be greater than 0")
    return [value / total for value in raw]


def _parse_prices(rows: list[dict[str, Any]], start_year: int, end_year: int) -> list[PriceRow]:
    parsed = []
    for row in rows:
        row_date = _parse_date(row["date"])
        close = float(row["close"])
        if start_year <= row_date.year <= end_year and close > 0:
            parsed.append(PriceRow(date=row_date, close=close))
    return sorted(parsed, key=lambda item: item.date)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _simulate_series(
    rows: list[PriceRow],
    buy_method: str,
    amount: float,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    first_trading_day_by_year = _first_trading_day_by_year(rows)
    first_available_day = rows[0].date
    shares = 0.0
    invested = 0.0
    peak_value = 0.0
    snapshots = []

    for row in rows:
        buy_amount = _buy_amount_for_day(
            row.date,
            buy_method,
            amount,
            start_year,
            end_year,
            first_trading_day_by_year,
            first_available_day,
        )
        if buy_amount:
            shares += buy_amount / row.close
            invested += buy_amount

        value = shares * row.close
        peak_value = max(peak_value, value)
        drawdown = 0.0 if peak_value == 0 else (value - peak_value) / peak_value
        snapshots.append(
            {
                "date": row.date.isoformat(),
                "year": row.date.year,
                "close": row.close,
                "shares": shares,
                "invested": invested,
                "value": value,
                "profit": value - invested,
                "return_rate": 0.0 if invested == 0 else (value - invested) / invested,
                "drawdown": drawdown,
            }
        )

    return snapshots


def _first_trading_day_by_year(rows: list[PriceRow]) -> dict[int, date]:
    first_days: dict[int, date] = {}
    for row in rows:
        first_days.setdefault(row.date.year, row.date)
    return first_days


def _buy_amount_for_day(
    row_date: date,
    buy_method: str,
    amount: float,
    start_year: int,
    end_year: int,
    first_trading_day_by_year: dict[int, date],
    first_available_day: date,
) -> float:
    if buy_method == "lump_sum":
        buy_day = first_trading_day_by_year.get(start_year, first_available_day)
        return amount if row_date == buy_day else 0.0

    if start_year <= row_date.year <= end_year and row_date == first_trading_day_by_year.get(row_date.year):
        return amount
    return 0.0


def _summarize(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        raise ValueError("No snapshots to summarize")

    first = snapshots[0]
    final = snapshots[-1]
    total_invested = final["invested"]
    final_value = final["value"]
    years = max((_parse_date(final["date"]) - _parse_date(first["date"])).days / 365.25, 1 / 365.25)
    return_rate = 0.0 if total_invested == 0 else (final_value - total_invested) / total_invested

    return {
        "start_date": first["date"],
        "end_date": final["date"],
        "total_invested": total_invested,
        "final_value": final_value,
        "profit": final_value - total_invested,
        "return_rate": return_rate,
        "annualized_return": pow(final_value / total_invested, 1 / years) - 1 if total_invested > 0 and final_value > 0 else 0.0,
        "max_drawdown": min(snapshot["drawdown"] for snapshot in snapshots),
    }
