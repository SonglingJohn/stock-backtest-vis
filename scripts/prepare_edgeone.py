"""Copy backend into cloud-functions for EdgeOne (lite data source, no akshare)."""

from __future__ import annotations

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


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=IGNORE)
    shutil.copy2(SRC / "data_source_lite.py", DST / "data_source.py")
    print(f"Synced {SRC} -> {DST} (lite data_source for EdgeOne)")


if __name__ == "__main__":
    main()
