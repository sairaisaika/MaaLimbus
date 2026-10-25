"""Does the packaged agent start?  Exit 1 when it dies before it can serve anything.

    python tools/verify_agent_start_up.py [--json]

Wraps `maalimbus.agent_probe`, so the harness and this check cannot disagree about what
"the agent started" means (D170).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus import agent_probe  # noqa: E402  (after the path is in place)

if __name__ == '__main__':
    raise SystemExit(agent_probe.main())
