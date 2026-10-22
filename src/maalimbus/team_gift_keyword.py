"""The gift target follows the saved team's own systems, not a constant.

`mirror_initial_keyword` is `saved` by default, which writes no override, so the run
used to fall back to the hard-coded `bleed` in `runner.Settings` (D32).  A charge/burn
team then bought bleed gifts, which pits the build against the team.  The saved team
names its own systems, so read them from the active run's team profile instead.
"""
import json
from pathlib import Path

from .storage import ProfileStore


def active_slot(directory):
    """The team slot the active run is using, or None when no run is in flight."""
    path = Path(directory) / 'user-run-ledger.json'
    if not path.exists():
        return None
    try:
        active = json.loads(path.read_text(encoding='utf-8')).get('active') or {}
    except (ValueError, OSError):
        return None
    slot = active.get('team')
    return slot if isinstance(slot, int) else None


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
