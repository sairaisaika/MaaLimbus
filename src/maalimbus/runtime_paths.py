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


CONFIG_FILES = ('user-team-profiles.json', 'user-mirror-settings.json', 'user-scores.json')


def plan_sync(source, target, names=CONFIG_FILES):
    """Which user preferences differ between a source and an installed copy.

    The installed tree keeps its own ``config/`` because the agent resolves
    ``data_directory`` from its own root (``runtime_paths.data_directory``), so a
    preference edited in the checkout never reaches a packaged run.  This reports
    the difference without touching either side; ``apply_sync`` is what copies, and
    it only ever copies files named here -- ledgers and transaction state stay put.
    """
    source, target = Path(source), Path(target)
    rows = []
    for name in names:
        here, there = source / name, target / name
        if not here.exists():
            rows.append({'name': name, 'action': 'missing', 'detail': str(here)})
        elif not there.exists():
            rows.append({'name': name, 'action': 'copied', 'detail': str(there)})
        elif here.read_bytes() == there.read_bytes():
            rows.append({'name': name, 'action': 'same', 'detail': str(there)})
        else:
            rows.append({'name': name, 'action': 'copied', 'detail': str(there)})
    return rows


def apply_sync(source, target, names=CONFIG_FILES):
    """Copy the files ``plan_sync`` reports as differing, and nothing else."""
    source, target = Path(source), Path(target)
    rows = plan_sync(source, target, names)
    for row in rows:
        if row['action'] == 'copied':
            target.mkdir(parents=True, exist_ok=True)
            (target / row['name']).write_bytes((source / row['name']).read_bytes())
    return rows
