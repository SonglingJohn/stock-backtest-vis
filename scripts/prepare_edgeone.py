"""Copy backend modules into cloud-functions for EdgeOne Pages deployment."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend"
DST = ROOT / "cloud-functions" / "backend"
IGNORE = shutil.ignore_patterns("server.py", "__pycache__", "*.pyc")


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=IGNORE)
    print(f"Synced {SRC} -> {DST}")


if __name__ == "__main__":
    main()
