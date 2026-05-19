from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from backend import api_handlers


ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"


class WorkbenchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._write_json(api_handlers.health())
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/stock-info":
            try:
                symbol = parse_qs(parsed.query).get("symbol", [""])[0]
                self._write_json(api_handlers.get_stock_info(symbol))
            except Exception as exc:
                self._write_json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/api/resolve-stock":
            try:
                query = parse_qs(parsed.query).get("q", [""])[0]
                self._write_json(api_handlers.resolve_stock(query))
            except Exception as exc:
                self._write_json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/api/market-indexes":
            self._write_json(api_handlers.get_market_indexes())
            return
        if parsed.path == "/api/preload-stock":
            try:
                query = parse_qs(parsed.query)
                self._write_json(
                    api_handlers.preload_stock(
                        query.get("symbol", [""])[0],
                        int(query.get("startYear", ["0"])[0]),
                        int(query.get("endYear", ["0"])[0]),
                    )
                )
            except Exception as exc:
                self._write_json({"error": str(exc)}, status=400)
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/backtest":
            self.send_error(404)
            return
        try:
            self._write_json(api_handlers.run_backtest_api(self._read_json()))
        except Exception as exc:
            self._write_json({"error": str(exc)}, status=400)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), WorkbenchHandler)
    print("A-share backtest workbench running at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
