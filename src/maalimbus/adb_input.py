"""A second input channel, used only when the MaaFW one cannot route.

Why it exists (measured 2026-10-23, run `evidence/runtime/packaged-mirror-20261023-161759`):
MaaFW answered `controller not found [req.controller_id=""]` for clicks sent through its
inserted-request path, and no Python code holds that id -- so the click never reached the
game.  `adb shell input tap` was observed working on the same pages, so it is kept here as
an explicit, optional channel rather than a silent replacement.

This module is deliberately small: it builds the command, runs it, and says what it did.
It is not a controller and it does not decide anything.
"""

import subprocess

DEFAULT_ADB = "D:/Program Files/Netease/MuMu/nx_main/adb.exe"


def tap_command(serial, x, y, *, adb=DEFAULT_ADB):
    """The argv for one tap. A serial-less call is refused instead of guessed."""
    if not str(serial or '').strip():
        raise ValueError('adb tap needs a device serial')
    return [adb, '-s', str(serial), 'shell', 'input', 'tap', str(int(x)), str(int(y))]


def tap(serial, x, y, *, adb=DEFAULT_ADB, run=subprocess.run, timeout=10):
    """Run one tap; return a small record of what happened."""
    argv = tap_command(serial, x, y, adb=adb)
    finished = run(argv, capture_output=True, text=True, timeout=timeout)
    code = getattr(finished, 'returncode', None)
    return {'command': argv, 'returncode': code, 'delivered': code == 0}
