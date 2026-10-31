"""把工作区收回到 2 GiB 预算内。默认预演，`--apply` 才删。"""
from __future__ import annotations

import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

from maalimbus.workspace import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
