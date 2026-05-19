"""Copy backend into cloud-functions for EdgeOne (lite data source, no akshare)."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend"
DST = ROOT / "cloud-functions" / "backend"
IGNORE = shutil.ignore_patterns(
    "server.py",
    "data_source.py",
    "data_source_lite.py",
    "__pycache__",
    "*.pyc",
)


def _bundle_stock_names(dst: Path) -> None:
    names_dst = dst / "stock_names.json"
    cache_names = ROOT / ".cache" / "stock-names.json"
    if cache_names.exists():
        shutil.copy2(cache_names, names_dst)
        print(f"Bundled stock names from {cache_names}")
        return

    lite_path = SRC / "data_source_lite.py"
    spec = importlib.util.spec_from_file_location("data_source_lite", lite_path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        names = module._fetch_a_share_names_em()
    except Exception as exc:
        print(f"warn: could not fetch stock names at build time: {exc}")
        return
    if not names:
        print("warn: stock name list empty, name search will use suggest API only")
        return
    names_dst.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Bundled {len(names)} stock names into {names_dst}")


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=IGNORE)
    shutil.copy2(SRC / "data_source_lite.py", DST / "data_source.py")
    _bundle_stock_names(DST)
    print(f"Synced {SRC} -> {DST} (lite data_source for EdgeOne)")


if __name__ == "__main__":
    main()
