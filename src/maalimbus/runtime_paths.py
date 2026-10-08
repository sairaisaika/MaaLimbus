"""Resolve the installed application, independently of cwd/PyInstaller extraction."""
import os
import json
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


def data_directory(root=ROOT):
    """Resolve an explicit local private-state binding, without copying ledgers."""
    base = Path(os.environ.get('MAALIMBUS_DATA_PATH', Path(root)/'config'))
    marker = base/'user-data-root.json'
    if not marker.exists():
        return base
    value = json.loads(marker.read_text(encoding='utf-8'))
    if set(value) != {'version', 'directory'} or value['version'] != 1:
        raise ValueError('Invalid private-state binding')
    target = Path(value['directory'])
    if not target.is_absolute() or not target.is_dir():
        raise ValueError('Private-state directory is unavailable')
    for parent in (target, *target.parents):
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('Linked private-state directory')
    if (target/'user-data-root.json').exists():
        raise ValueError('Chained private-state binding')
    return target


def ledger_path(value, root=ROOT):
    path = Path(str(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == 'config':
        if '..' in path.parts:
            raise ValueError('Unsafe private ledger path')
        return data_directory(root).joinpath(*path.parts[1:])
    return Path(root)/path
