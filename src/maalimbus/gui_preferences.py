"""Read the choices a player made in the GUI, so a driver runs the same task.

The driver used to start `MirrorTask` with its own defaults while the GUI held the
player's real choices (team 2, Charge+Tremor, gift search on).  That produced runs
whose team and build were not the configured ones -- a second source of truth for
"which team and which build", which is exactly the class of defect that makes a
run look like a game problem when it is a configuration problem.

This module only *reads*: it never invents a keyword and never changes a setting.
A missing field stays missing (`None`), so a caller can tell "not configured" from
"configured to the default".
"""
import json
from pathlib import Path

DEFAULT = Path('dist/MaaLimbus/config/mxu-MaaLimbus.json')
FIELDS = ('mirror_team_mode', 'mirror_single_team', 'mirror_initial_keyword',
          'mirror_gift_search', 'mirror_run_count')


def _cases(value):
    return value.get('caseName') if isinstance(value, dict) else None


def read(path=DEFAULT):
    """Return the run preferences the GUI persisted, or `{}` when unreadable."""
    try:
        config = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    instances = config.get('instances') or []
    if not instances:
        return {}
    options = (instances[0].get('tasks') or [{}])[0].get('optionValues') or {}
    out = {field: _cases(options.get(field)) for field in FIELDS}
    team = out.get('mirror_single_team')
    if isinstance(team, str) and team.isdigit():
        out['mirror_single_team'] = int(team)
    elif not isinstance(team, int):
        out['mirror_single_team'] = None
    team_number = out.get('mirror_single_team')
    globals_ = config.get('globalOptionValues') or {}
    if team_number:
        out['team_name'] = _cases(globals_.get(f'global_team_{team_number}_name'))
        systems = globals_.get(f'global_team_{team_number}_systems') or {}
        out['team_systems'] = systems.get('caseName') if isinstance(systems, dict) else None
    else:
        out['team_name'] = None
        out['team_systems'] = None
    return out


def describe(prefs):
    """One line for a run's evidence, so a run states what it was told to do."""
    if not prefs:
        return 'no_gui_preferences'
    team = prefs.get('mirror_single_team')
    if team:
        return f'team {team} ({prefs.get("team_systems") or "systems unknown"})'
    return f'team mode {prefs.get("mirror_team_mode") or "unknown"}'
