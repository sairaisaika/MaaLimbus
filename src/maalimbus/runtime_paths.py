"""Resolve the installed application, independently of cwd/PyInstaller extraction."""
import os
from pathlib import Path
import sys


def application_root(*, executable=None, frozen=None, source_file=None, override=None):
    if override is not None:
        return Path(override).resolve()
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if frozen:
        # Both Agent and Runner live in an immediate subdirectory of the app.
        return Path(executable or sys.executable).resolve().parents[1]
    return Path(source_file or __file__).resolve().parents[2]


ROOT = application_root(override=None if getattr(sys, 'frozen', False)
                        else os.environ.get('MAALIMBUS_ROOT'))
