"""Recognise a locked or sleeping screen, and say how to wake it.

A run that starts while the device is locked captures the lock screen, classifies it
as UNKNOWN, and spends its whole budget waiting for a page that will never come.  The
device can say whether it is locked, so the launch path can ask instead of guessing.
"""
from __future__ import annotations

KEYGUARD_ON = 'KeyguardShowing'
KEYGUARD_OFF = 'KeyguardShowing=false'

# TO_WAKE: `WAKEUP` turns the display on without toggling it, unlike `POWER`.
TO_WAKE = (('shell', 'input', 'keyevent', '224'), ('shell', 'wm', 'dismiss-keyguard'))


def is_locked(window_dump: str | None) -> bool | None:
    """True/False from a `dumpsys window` dump, or None when it cannot be told."""
    if not window_dump:
        return None
    if KEYGUARD_OFF in window_dump:
        return False
    if KEYGUARD_ON in window_dump:
        return True
    return None


def wake_commands(locked: bool | None) -> tuple:
    """The commands that may be spent: none when the screen is known to be awake."""
    if locked is False:
        return ()
    return TO_WAKE


def ensure_awake(run_adb, *, dump=('shell', 'dumpsys', 'window')):
    """Ask the device once, wake it only if needed, and report what was seen.

    `run_adb(argv) -> str` is injected so this stays testable without a device.
    Returns {'locked': True|False|None, 'woken': bool}.
    """
    try:
        locked = is_locked(run_adb(dump))
    except (OSError, RuntimeError, AttributeError, TypeError):
        locked = None
    woken = False
    for argv in wake_commands(locked):
        try:
            run_adb(argv)
            woken = True
        except (OSError, RuntimeError, AttributeError, TypeError):
            break
    return {'locked': locked, 'woken': woken}
