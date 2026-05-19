"""Lightweight market data for EdgeOne (requests only, no akshare/pandas)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


def _project_root() -> Path:
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / "frontend").is_dir() and (candidate / "requirements.txt").is_file():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent


_ROOT = _project_root()
CACHE_DIR = _ROOT / ".cache" / "prices"
NAME_CACHE_FILE = _ROOT / ".cache" / "stock-names.json"
MARKET_INDEX_CACHE_FILE = _ROOT / ".cache" / "market-indexes.json"
PRICE_ADJUST = "hfq"
_REQUEST_TIMEOUT = 30

FALLBACK_MARKET_INDEXES = [
    {"code": "000001", "name": "上证指数", "value": 4131.53, "change": -3.86, "change_pct": -0.09, "stale": True},
    {"code": "399001", "name": "深证成指", "value": 15530.23, "change": -31.14, "change_pct": -0.20, "stale": True},
    {"code": "399006", "name": "创业板", "value": 3914.88, "change": -14.18, "change_pct": -0.36, "stale": True},
    {"code": "000300", "name": "沪深300", "value": 3928.44, "change": 18.62, "change_pct": 0.48, "stale": True},
    {"code": "000688", "name": "科创50", "value": 1008.16, "change": 6.20, "change_pct": 0.62, "stale": True},
    {"code": "899050", "name": "北证50", "value": 1265.48, "change": -5.18, "change_pct": -0.41, "stale": True},
]

_EM_UT = "7eea3edcaed734bea9cbfc24409ed99"
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AShareBacktest/1.0)",
    "Referer": "https://quote.eastmoney.com/",
}


def load_a_share_prices(symbol: str, start_year: int, end_year: int, cache_dir: Path = CACHE_DIR) -> list[dict[str, Any]]:
    normalized_symbol = normalize_symbol(symbol)
    cache_file = cache_dir / f"{normalized_symbol}-{start_year}-{end_year}-{PRICE_ADJUST}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    covering_rows = _load_covering_cache(normalized_symbol, start_year, end_year, cache_dir)
    if covering_rows:
        return covering_rows

    legacy_rows = _load_covering_cache(normalized_symbol, start_year, end_year, cache_dir, adjust="qfq")
    if legacy_rows:
        return _rebase_non_positive_prices(legacy_rows)

    try:
        rows = _fetch_stock_kline_em(normalized_symbol, start_year, end_year)
    except Exception as exc:
        raise RuntimeError(f"行情数据暂时连接失败，且没有可用缓存：{normalized_symbol} {start_year}-{end_year}") from exc
    if not rows:
        raise RuntimeError(f"No price rows returned for {normalized_symbol}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def _load_covering_cache(
    symbol: str,
    start_year: int,
    end_year: int,
    cache_dir: Path,
    adjust: str = PRICE_ADJUST,
) -> list[dict[str, Any]]:
    if not cache_dir.exists():
        return []

    best_match: tuple[int, Path] | None = None
    for file in cache_dir.glob(f"{symbol}-*-*-{adjust}.json"):
        parts = file.stem.split("-")
        if len(parts) != 4:
            continue
        try:
            cached_start = int(parts[1])
            cached_end = int(parts[2])
        except ValueError:
            continue
        if cached_start <= start_year and cached_end >= end_year:
            span = cached_end - cached_start
            if best_match is None or span < best_match[0]:
                best_match = (span, file)

    if best_match is None:
        return []

    rows = json.loads(best_match[1].read_text(encoding="utf-8"))
    return [
        row
        for row in rows
        if start_year <= datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").year <= end_year
    ]


def _rebase_non_positive_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    min_close = min(float(row["close"]) for row in rows)
    if min_close > 0:
        return rows
    offset = abs(min_close) + 1
    return [{**row, "close": float(row["close"]) + offset} for row in rows]


def normalize_symbol(symbol: str) -> str:
    cleaned = "".join(ch for ch in symbol.strip() if ch.isalnum())
    if len(cleaned) < 6:
        raise ValueError("股票代码至少需要 6 位")
    return cleaned[-6:]


def load_a_share_names(cache_file: Path = NAME_CACHE_FILE) -> dict[str, str]:
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    try:
        names = _fetch_a_share_names_em()
    except Exception:
        return {}

    if names:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    return names


def resolve_stock_query(query: str, names: dict[str, str] | None = None) -> dict[str, str]:
    text = str(query or "").strip()
    if not text:
        raise ValueError("请输入股票代码或股票名称")

    names = names if names is not None else load_a_share_names()
    code_part = "".join(ch for ch in text if ch.isdigit())
    if len(code_part) >= 6:
        symbol = normalize_symbol(code_part)
        return {"symbol": symbol, "name": names.get(symbol, symbol)}

    exact = [(symbol, name) for symbol, name in names.items() if name == text]
    if exact:
        symbol, name = exact[0]
        return {"symbol": symbol, "name": name}

    partial = [(symbol, name) for symbol, name in names.items() if text in name]
    if partial:
        symbol, name = partial[0]
        return {"symbol": symbol, "name": name}

    raise ValueError(f"没有找到股票：{text}")


def load_stock_info(symbol: str, cache_dir: Path = CACHE_DIR) -> dict[str, Any]:
    normalized_symbol = normalize_symbol(symbol)
    names = load_a_share_names()
    rows = _load_any_cached_rows(normalized_symbol, cache_dir)
    if not rows:
        current_year = datetime.now().year
        rows = load_a_share_prices(normalized_symbol, 1990, current_year, cache_dir=cache_dir)

    first_date = min(str(row["date"])[:10] for row in rows)
    return {
        "symbol": normalized_symbol,
        "name": names.get(normalized_symbol, normalized_symbol),
        "listing_date": first_date,
        "listing_year": int(first_date[:4]),
    }


def load_market_indexes(cache_file: Path = MARKET_INDEX_CACHE_FILE) -> list[dict[str, Any]]:
    try:
        rows = _fetch_market_indexes_em()
    except Exception:
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        return FALLBACK_MARKET_INDEXES
    if not rows:
        return FALLBACK_MARKET_INDEXES

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def load_index_prices(symbol: str, start_year: int, end_year: int, cache_dir: Path = CACHE_DIR) -> list[dict[str, Any]]:
    normalized_symbol = normalize_symbol(symbol)
    cache_file = cache_dir / f"index-{normalized_symbol}-{start_year}-{end_year}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    covering_rows = _load_covering_index_cache(normalized_symbol, start_year, end_year, cache_dir)
    if covering_rows:
        return covering_rows

    rows = _fetch_index_kline_em(normalized_symbol, start_year, end_year)
    if not rows:
        raise RuntimeError(f"No index rows returned for {normalized_symbol}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def market_index_names() -> dict[str, str]:
    return {item["code"]: item["name"] for item in FALLBACK_MARKET_INDEXES}


def _load_any_cached_rows(symbol: str, cache_dir: Path) -> list[dict[str, Any]]:
    if not cache_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for file in cache_dir.glob(f"{symbol}-*-*-*.json"):
        try:
            rows.extend(json.loads(file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return rows


def _load_covering_index_cache(symbol: str, start_year: int, end_year: int, cache_dir: Path) -> list[dict[str, Any]]:
    if not cache_dir.exists():
        return []

    best_match: tuple[int, Path] | None = None
    for file in cache_dir.glob(f"index-{symbol}-*-*.json"):
        parts = file.stem.split("-")
        if len(parts) != 4:
            continue
        try:
            cached_start = int(parts[2])
            cached_end = int(parts[3])
        except ValueError:
            continue
        if cached_start <= start_year and cached_end >= end_year:
            span = cached_end - cached_start
            if best_match is None or span < best_match[0]:
                best_match = (span, file)

    if best_match is None:
        return []

    rows = json.loads(best_match[1].read_text(encoding="utf-8"))
    return [
        row
        for row in rows
        if start_year <= datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").year <= end_year
    ]


def _em_stock_secid(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9")):
        return f"1.{symbol}"
    if symbol.startswith(("4", "8")):
        return f"0.{symbol}"
    return f"0.{symbol}"


def _em_index_secid(symbol: str) -> str:
    if symbol.startswith(("399", "159", "899")):
        return f"0.{symbol}"
    return f"1.{symbol}"


def _fetch_stock_kline_em(symbol: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    response = requests.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": _EM_UT,
            "klt": "101",
            "fqt": "2",
            "secid": _em_stock_secid(symbol),
            "beg": f"{start_year}0101",
            "end": f"{end_year}1231",
        },
        headers=_EM_HEADERS,
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    klines = (response.json().get("data") or {}).get("klines") or []
    rows = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        rows.append({"date": parts[0], "close": float(parts[2])})
    return rows


def _fetch_index_kline_em(symbol: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    response = requests.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": _EM_UT,
            "klt": "101",
            "fqt": "0",
            "secid": _em_index_secid(symbol),
            "beg": f"{start_year}0101",
            "end": f"{end_year}1231",
        },
        headers=_EM_HEADERS,
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    klines = (response.json().get("data") or {}).get("klines") or []
    rows = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        date_text = parts[0]
        if not (start_year <= datetime.strptime(date_text, "%Y-%m-%d").year <= end_year):
            continue
        rows.append({"date": date_text, "close": float(parts[2])})
    return rows


def _fetch_market_indexes_em() -> list[dict[str, Any]]:
    wanted = {item["code"] for item in FALLBACK_MARKET_INDEXES}
    fs_parts = [f"i:{_em_index_secid(code)}" for code in wanted]
    response = requests.get(
        "https://push2.eastmoney.com/api/qt/ulist.np/get",
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f12,f14,f2,f3,f4",
            "secids": ",".join(fs_parts),
        },
        headers=_EM_HEADERS,
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    items = (response.json().get("data") or {}).get("diff") or []
    rows = []
    for item in items:
        code = normalize_symbol(str(item.get("f12", "")))
        if code not in wanted:
            continue
        rows.append(
            {
                "code": code,
                "name": str(item.get("f14", code)),
                "value": float(item.get("f2", 0) or 0),
                "change": float(item.get("f4", 0) or 0),
                "change_pct": float(item.get("f3", 0) or 0),
                "stale": False,
            }
        )
    sort_order = {item["code"]: index for index, item in enumerate(FALLBACK_MARKET_INDEXES)}
    return sorted(rows, key=lambda item: sort_order.get(item["code"], 99))


def _fetch_a_share_names_em() -> dict[str, str]:
    response = requests.get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1",
            "pz": "50000",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:1+t:4",
            "fields": "f12,f14",
        },
        headers=_EM_HEADERS,
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    items = (response.json().get("data") or {}).get("diff") or []
    names: dict[str, str] = {}
    for item in items:
        code = normalize_symbol(str(item.get("f12", "")))
        name = str(item.get("f14", "")).strip()
        if code and name:
            names[code] = name
    return names
