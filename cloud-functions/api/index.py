from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, request

_cf_root = Path(__file__).resolve().parents[1]
if str(_cf_root) not in sys.path:
    sys.path.insert(0, str(_cf_root))

from backend import api_handlers  # noqa: E402

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(api_handlers.health())


@app.get("/stock-info")
def stock_info():
    try:
        return jsonify(api_handlers.get_stock_info(request.args.get("symbol", "")))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/resolve-stock")
def resolve_stock():
    try:
        return jsonify(api_handlers.resolve_stock(request.args.get("q", "")))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/market-indexes")
def market_indexes():
    return jsonify(api_handlers.get_market_indexes())


@app.get("/preload-stock")
def preload_stock():
    try:
        return jsonify(
            api_handlers.preload_stock(
                request.args.get("symbol", ""),
                int(request.args.get("startYear", "0")),
                int(request.args.get("endYear", "0")),
            )
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/backtest")
def backtest():
    try:
        return jsonify(api_handlers.run_backtest_api(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
