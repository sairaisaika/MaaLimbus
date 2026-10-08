"""Seed native global editors from existing builds without replacing user edits."""
from copy import deepcopy


def seed_editors(config, interface, teams):
    result = deepcopy(config)
    values = result.setdefault('globalOptionValues', {})
    changed = []
    for team in teams:
        prefix = f'global_team_{team.slot}'
        if len(team.deployment) != 12:
            continue
        mode = values.get(prefix)
        if mode and mode != {'type': 'select', 'caseName': 'saved'}:
            continue
        system = interface['option'][prefix+'_systems']
        match = next((c['name'] for c in system['cases']
                      if frozenset(c['name'].split('+')) == team.keywords), None)
        if match is None:
            continue
        desired = {prefix: {'type':'select','caseName':'saved'},
                   prefix+'_name': {'type':'input','values':{'name':team.name or f'Team {team.slot}'}},
                   prefix+'_systems': {'type':'select','caseName':match}}
        desired.update({prefix+f'_order_{n}': {'type':'select','caseName':s}
                        for n,s in enumerate(team.deployment,1)})
        # Check the whole editor first. A changed name/order/system means the
        # user's UI is authoritative; do not silently replace any of its fields.
        eligible = True
        for key, value in desired.items():
            spec = interface['option'][key]
            default = ({'type':'input','values':{i['name']:i['default'] for i in spec['inputs']}}
                       if spec['type']=='input' else {'type':'select','caseName':spec['default_case']})
            if key in values and values[key] not in (default, value):
                eligible = False
                break
        if eligible:
            for key,value in desired.items():
                if values.get(key) != value:
                    values[key] = value
                    changed.append(key)
    return result, changed
