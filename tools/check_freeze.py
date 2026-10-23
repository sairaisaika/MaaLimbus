"""Fail when the frozen app does not carry the current source.

Every live run executes `dist/MaaLimbus`, never `src/`.  A fix that is committed,
tested and *believed* is still invisible to the device until the app is refrozen,
and a corpus recorded in between is evidence about the old code.  That happened on
2026-10-23: the heartbeat, the build fingerprint and the silent-death metric were
all committed while `dist` still sat five commits back, so a whole round of live
runs could not have contained them.

Usage:
    python tools/check_freeze.py           # exit 1 when stale
    python tools/check_freeze.py --json    # machine form for scripts
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_INFO = ROOT / 'dist' / 'MaaLimbus' / 'build-info.json'


def head():
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(ROOT), capture_output=True,
                          text=True, check=True).stdout.strip()


def frozen():
    if not BUILD_INFO.exists():
        return None
    try:
        return json.loads(BUILD_INFO.read_text(encoding='utf-8')).get('source_commit')
    except (OSError, ValueError):
        return None


_UNSET = object()


def verdict(head_sha=_UNSET, frozen_sha=_UNSET):
    """``{'state': 'current'|'stale'|'missing', ...}`` -- pure, so it is testable.

    Defaults are a sentinel, not ``None``: ``None`` is the *answer* for "there is no
    frozen build", and conflating it with "the caller said nothing" is exactly how a
    guard test passes while the guard is inert.
    """
    head_sha = head() if head_sha is _UNSET else head_sha
    frozen_sha = frozen() if frozen_sha is _UNSET else frozen_sha
    if not frozen_sha:
        return {'state': 'missing', 'head': head_sha, 'frozen': None,
                'reason': 'no dist build-info; run build/refreeze_agent.py'}
    if frozen_sha == head_sha:
        return {'state': 'current', 'head': head_sha, 'frozen': frozen_sha, 'reason': None}
    behind = subprocess.run(['git', 'rev-list', '--count', f'{frozen_sha}..{head_sha}'],
                            cwd=str(ROOT), capture_output=True, text=True)
    commits = int(behind.stdout.strip() or 0) if behind.returncode == 0 else None
    return {'state': 'stale', 'head': head_sha, 'frozen': frozen_sha, 'behind': commits,
            'reason': 'the frozen app predates HEAD; a live run would test old code'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    report = verdict()
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"frozen {str(report['frozen'])[:8]}  head {report['head'][:8]}  {report['state']}")
        if report['reason']:
            print(report['reason'])
    return 0 if report['state'] == 'current' else 1


if __name__ == '__main__':
    raise SystemExit(main())
