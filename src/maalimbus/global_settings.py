"""Apply native MXU global build edits without performing device input.

Only explicitly edited slots replace saved fields. Other build metadata and
rotation order remain intact. Validate the entire edit before replacing the file.
"""
from dataclasses import replace
from .policies import Team
from .storage import ProfileStore, SINNERS, KEYWORDS, read_json


def collect_builds(get_node):
    """Read distinct nodes: ordinary MXU overrides replace action params shallowly."""
    result = {}
    for slot in range(1, 21):
        prefix = f'Global_global_team_{slot}'
        enabled = get_node(prefix)['attach']['global_build']['edit']
        if type(enabled) is not bool:
            raise ValueError('Invalid build edit switch')
        if not enabled:
            continue
        value = {'edit': True, 'deployment': {}}
        for suffix in ('name', 'systems'):
            value.update(get_node(prefix+'_'+suffix)['attach']['global_build'])
        for n in range(1, 13):
            value['deployment'].update(get_node(prefix+f'_order_{n}')['attach']['global_build']['deployment'])
        result[str(slot)] = value
    return result


def apply_builds(directory, edits):
    if not isinstance(edits, dict):
        raise ValueError('Global build edits must be an object')
    store = ProfileStore(directory / 'user-team-profiles.json')
    teams = list(store.load()) if store.path.exists() else []
    changed = []
    ledger = directory / 'user-run-ledger.json'
    active = read_json(ledger).get('active') if ledger.exists() else None
    for key, edit in edits.items():
        if not isinstance(key, str) or not key.isdecimal() or not 1 <= int(key) <= 20:
            raise ValueError('Unknown global build slot')
        if not isinstance(edit, dict) or edit.get('edit') is not True:
            raise ValueError('Build replacement must be explicitly selected')
        slot = int(key)
        name, keywords, order = edit.get('name'), edit.get('keywords'), edit.get('deployment')
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('Give the saved team a name of 1..80 characters')
        if (not isinstance(keywords, list) or not keywords or
                len(set(keywords)) != len(keywords) or not set(keywords) <= set(KEYWORDS)):
            raise ValueError('Choose known, distinct team systems')
        if (not isinstance(order, dict) or set(order) != {str(n) for n in range(1, 13)}):
            raise ValueError('Choose all twelve deployment positions')
        deployment = tuple(order[str(n)] for n in range(1, 13))
        if set(deployment) != set(SINNERS) or len(set(deployment)) != 12:
            raise ValueError('Each sinner must appear exactly once')
        old = next((t for t in teams if t.slot == slot), None)
        new = replace(old or Team(slot, frozenset()), name=name.strip(),
                      keywords=frozenset(keywords), deployment=deployment)
        if active and active.get('team') == slot and old != new:
            raise ValueError('Finish the active run before editing its team')
        if old != new:
            if old is None:
                teams.append(new)
            else:
                teams[teams.index(old)] = new
            changed.append(slot)
    if changed:
        store.save(teams)
    return changed
