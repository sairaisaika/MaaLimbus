"""Session-level guards for tests that need the real controller lease to be free.

Twice in one session the full suite went red for the same reason: a live
`MaaLimbusAgent` held `%LOCALAPPDATA%/MaaLimbus/controller.lock`, so the two tests
that prove lease exclusion saw an owner that was not theirs.  A failure that is
caused by the environment and repeats is a missing fixture, not a flaky test: it
skips with the holder's pid named, so the operator can act on it instead of
re-deriving why a red suite is fine.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

LEASE = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'MaaLimbus', 'controller.lock')

NEEDS_FREE_LEASE = (
    'tests/test_controller_lease.py::test_cli_and_agent_cannot_acquire_another_process_controller',
    'tests/test_update_install.py::test_real_controller_lock_blocks_installation',
)


def lease_holder():
    """The owning pid of the real lease, or ``None`` when nothing holds it."""
    if not os.path.exists(LEASE):
        return None
    try:
        raw = open(LEASE, 'r', encoding='utf-8').read().strip()
    except OSError:
        # The lock exists but cannot be read -- that is the *held* case, not the free
        # one.  Treating it as absent is why the guard had no effect while a live
        # agent held the file (measured 2026-10-23).
        return -1
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    # The lock has been written as both a bare pid and a dict over time; accepting
    # only one shape turned a guard into an INTERNALERROR (measured 2026-10-23).
    if isinstance(parsed, int):
        return parsed
    if isinstance(parsed, dict):
        return parsed.get('pid')
    return None


def is_alive(pid):
    if not pid:
        return False
    check = subprocess.run(['tasklist', '/FI', f'PID eq {int(pid)}'],
                           capture_output=True, text=True)
    return str(pid) in (check.stdout or '')


def pytest_collection_modifyitems(config, items):
    pid = lease_holder()
    if not pid:
        return
    # These two tests need the lease to be *absent*, not merely unowned: a lock file
    # left behind by a killed process still blocks them (measured twice on 2026-10-23,
    # the second time with a dead pid 11172).  Report the state so the operator knows
    # whether to kill a process or just delete a file.
    state = 'unknown' if pid == -1 else ('live' if is_alive(pid) else 'stale')
    reason = (f'the real controller lease is present (pid {pid}, {state}); remove it to '
              'exercise lease exclusion')
    for item in items:
        if item.nodeid in NEEDS_FREE_LEASE:
            item.add_marker(pytest.mark.skip(reason=reason))
