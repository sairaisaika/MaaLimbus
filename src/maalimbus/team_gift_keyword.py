"""The gift target follows the saved team's own systems, not a constant.

`mirror_initial_keyword` is `saved` by default, which writes no override, so the run
used to fall back to the hard-coded `bleed` in `runner.Settings` (D32).  A charge/burn
team then bought bleed gifts, which pits the build against the team.  The saved team
names its own systems, so read them from the active run's team profile instead.
"""
import json
from pathlib import Path

from .storage import ProfileStore


SETTING_FILES = ('mxu-MaaLimbus.json', 'user-settings.json')


def _find(mapping, key):
    """The first value stored under `key` anywhere in the settings tree."""
    if isinstance(mapping, dict):
        if key in mapping:
            return mapping[key]
        for value in mapping.values():
            found = _find(value, key)
            if found is not None:
                return found
    elif isinstance(mapping, list):
        for value in mapping:
            found = _find(value, key)
            if found is not None:
                return found
    return None


def configured_slot(directory):
    """The team slot the *task settings* name, e.g. `mirror_single_team = 2`.

    The game switches to this slot itself when the task starts, so it -- not the run
    ledger -- is what the next run will actually be playing.  `single` picks the named
    slot; any other mode leaves the choice to the rotation, so this returns None.
    """
    for name in SETTING_FILES:
        for base in (Path(directory), Path(directory).parent / 'dist/MaaLimbus/config',
                     Path(directory).parent / 'config'):
            path = base / name
            if not path.exists():
                continue
            try:
                settings = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            mode = _find(settings, 'mirror_team_mode')
            mode = mode.get('caseName') if isinstance(mode, dict) else mode
            slot = _find(settings, 'mirror_single_team')
            slot = slot.get('caseName') if isinstance(slot, dict) else slot
            if str(mode).lower() != 'single':
                return None
            try:
                return int(slot)
            except (TypeError, ValueError):
                return None
    return None


def active_slot(directory):
    """The team slot the next run will play: the task setting, else the run ledger."""
    slot = configured_slot(directory)
    if slot is not None:
        return slot
    path = Path(directory) / 'user-run-ledger.json'
    if not path.exists():
        return None
    try:
        active = json.loads(path.read_text(encoding='utf-8')).get('active') or {}
    except (ValueError, OSError):
        return None
    slot = active.get('team')
    return slot if isinstance(slot, int) else None


def systems(directory):
    """Every system the active team is built around, e.g. `('charge', 'tremor')`.

    A team like charge+tremor has two; picking one of them would be the same arbitrary
    choice that made the old constant wrong.  The planner still accepts a single
    keyword, so `from_active_team` takes the first -- the set is what a caller should
    use once the planner can rank on it.
    """
    slot = active_slot(directory)
    if slot is None:
        return ()
    store = ProfileStore(Path(directory) / 'user-team-profiles.json')
    if not store.path.exists():
        return ()
    for team in store.load():
        if getattr(team, 'slot', None) != slot:
            continue
        for field in ('formation_keywords', 'keywords'):
            names = sorted(n.strip().lower() for n in (getattr(team, field, None) or ())
                           if isinstance(n, str) and n.strip())
            if names:
                return tuple(names)
    return ()


def from_active_team(directory):
    """The gift keyword the active team's own profile asks for, else None.

    `formation_keywords` is what the team is built around (``Charge``/``Tremor`` for
    the charge team, ``Bleed`` for the bleed one); `keywords` is the wider set.  A
    formation keyword is preferred because a gift that serves the formation is the
    one the build was written for.
    """
    slot = active_slot(directory)
    if slot is None:
        return None
    store = ProfileStore(Path(directory) / 'user-team-profiles.json')
    if not store.path.exists():
        return None
    for team in store.load():
        if getattr(team, 'slot', None) != slot:
            continue
        # The profile stores these as frozensets, so pick by sorted order rather than
        # by set iteration order: the same team must always yield the same keyword.
        for field in ('formation_keywords', 'keywords'):
            names = sorted(n.strip().lower() for n in (getattr(team, field, None) or ())
                           if isinstance(n, str) and n.strip())
            if names:
                return names[0]
    return None
