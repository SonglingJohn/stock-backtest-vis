from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


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

FALLBACK_MARKET_INDEXES = [
    {"code": "000001", "name": "上证指数", "value": 4131.53, "change": -3.86, "change_pct": -0.09, "stale": True},
    {"code": "399001", "name": "深证成指", "value": 15530.23, "change": -31.14, "change_pct": -0.20, "stale": True},
    {"code": "399006", "name": "创业板", "value": 3914.88, "change": -14.18, "change_pct": -0.36, "stale": True},
    {"code": "000300", "name": "沪深300", "value": 3928.44, "change": 18.62, "change_pct": 0.48, "stale": True},
    {"code": "000688", "name": "科创50", "value": 1008.16, "change": 6.20, "change_pct": 0.62, "stale": True},
    {"code": "899050", "name": "北证50", "value": 1265.48, "change": -5.18, "change_pct": -0.41, "stale": True},
]


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
        rows = _fetch_akshare_prices(normalized_symbol, start_year, end_year)
    except Exception as exc:
        raise RuntimeError(f"行情数据暂时连接失败，且没有可用缓存：{normalized_symbol} {start_year}-{end_year}") from exc
    if not rows:
        raise RuntimeError(f"No AKShare price rows returned for {normalized_symbol}")

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
    return [
        {
            **row,
            "close": float(row["close"]) + offset,
        }
        for row in rows
    ]


def normalize_symbol(symbol: str) -> str:
    cleaned = "".join(ch for ch in symbol.strip() if ch.isalnum())
    if len(cleaned) < 6:
        raise ValueError("股票代码至少需要 6 位")
    return cleaned[-6:]


def load_a_share_names(cache_file: Path = NAME_CACHE_FILE) -> dict[str, str]:
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    try:
        import akshare as ak  # type: ignore

        frame = ak.stock_info_a_code_name()
    except Exception:
        return {}

    code_column = _find_column(frame.columns, ["code", "代码"])
    name_column = _find_column(frame.columns, ["name", "名称"])
    names = {
        normalize_symbol(str(item[code_column])): str(item[name_column])
        for _, item in frame.iterrows()
    }
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
        rows = _fetch_market_indexes()
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

    rows = _fetch_index_prices(normalized_symbol, start_year, end_year)
    if not rows:
        raise RuntimeError(f"No AKShare index rows returned for {normalized_symbol}")

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


def _fetch_market_indexes() -> list[dict[str, Any]]:
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缺少 AKShare。请先运行：py -m pip install -r requirements.txt") from exc

    frame = ak.stock_zh_index_spot_em()
    if frame is None or frame.empty:
        return []

    code_column = _find_column(frame.columns, ["代码", "code"])
    name_column = _find_column(frame.columns, ["名称", "name"])
    value_column = _find_column(frame.columns, ["最新价", "最新", "price", "close"])
    pct_column = _find_column(frame.columns, ["涨跌幅", "change_pct", "pct_chg"])
    change_column = _find_column(frame.columns, ["涨跌额", "change"])
    wanted = {item["code"] for item in FALLBACK_MARKET_INDEXES}
    rows = []
    for _, item in frame.iterrows():
        code = normalize_symbol(str(item[code_column]))
        if code not in wanted:
            continue
        rows.append(
            {
                "code": code,
                "name": str(item[name_column]),
                "value": float(item[value_column]),
                "change": float(item[change_column]),
                "change_pct": float(item[pct_column]),
                "stale": False,
            }
        )

    sort_order = {item["code"]: index for index, item in enumerate(FALLBACK_MARKET_INDEXES)}
    return sorted(rows, key=lambda item: sort_order.get(item["code"], 99)) or FALLBACK_MARKET_INDEXES


def _fetch_index_prices(symbol: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缺少 AKShare。请先运行：py -m pip install -r requirements.txt") from exc

    try:
        frame = ak.stock_zh_index_daily(symbol=_sina_index_symbol(symbol))
    except Exception:
        frame = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=f"{start_year}0101",
            end_date=f"{end_year}1231",
        )
    if frame is None or frame.empty:
        return []

    date_column = _find_column(frame.columns, ["日期", "date"])
    close_column = _find_column(frame.columns, ["收盘", "close"])
    rows = []
    for _, item in frame.iterrows():
        date_text = _format_date(item[date_column])
        if not (start_year <= datetime.strptime(date_text, "%Y-%m-%d").year <= end_year):
            continue
        rows.append(
            {
                "date": date_text,
                "close": float(item[close_column]),
            }
        )
    return rows


def _sina_index_symbol(symbol: str) -> str:
    if symbol.startswith(("399", "159")):
        return f"sz{symbol}"
    if symbol.startswith("899"):
        return f"bj{symbol}"
    return f"sh{symbol}"


def _fetch_akshare_prices(symbol: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:
        raise RuntimeError("缺少 AKShare。请先运行：py -m pip install -r requirements.txt") from exc

    start_date = f"{start_year}0101"
    end_date = f"{end_year}1231"
    errors = []
    fetchers = [
        lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=PRICE_ADJUST,
        ),
        lambda: ak.stock_zh_a_daily(
            symbol=_prefixed_stock_symbol(symbol),
            start_date=start_date,
            end_date=end_date,
            adjust=PRICE_ADJUST,
        ),
        lambda: ak.stock_zh_a_hist_tx(
            symbol=_prefixed_stock_symbol(symbol),
            start_date=start_date,
            end_date=end_date,
            adjust=PRICE_ADJUST,
        ),
    ]

    frame = None
    for fetch in fetchers:
        try:
            candidate = fetch()
        except Exception as exc:
            errors.append(exc)
            continue
        if candidate is not None and not candidate.empty:
            frame = candidate
            break
    if frame is None or frame.empty:
        if errors:
            raise errors[-1]
        return []

    date_column = _find_column(frame.columns, ["日期", "date"])
    close_column = _find_column(frame.columns, ["收盘", "close"])
    rows = []
    for _, item in frame.iterrows():
        rows.append(
            {
                "date": _format_date(item[date_column]),
                "close": float(item[close_column]),
            }
        )
    return rows


def _prefixed_stock_symbol(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9")):
        return f"sh{symbol}"
    if symbol.startswith(("4", "8")):
        return f"bj{symbol}"
    return f"sz{symbol}"


def _find_column(columns: list[str], candidates: list[str]) -> str:
    lowered = {str(column).lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    raise RuntimeError(f"AKShare response missing column: {'/'.join(candidates)}")


def _format_date(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value)[:10]
    if "/" in text:
        return datetime.strptime(text, "%Y/%m/%d").strftime("%Y-%m-%d")
    return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
