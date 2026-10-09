"""Mirror task star rules reference saved builds and explicit spending limits."""
from dataclasses import replace
from .storage import ProfileStore, read_json, write_json


def plan(value):
    choices=value.get('choices')
    budget=value.get('budget')
    if (not isinstance(choices,list) or len(choices)>10 or
        any(type(n) is not int or not 0<=n<=9 for n in choices) or len(set(choices))!=len(choices)):
        raise ValueError('Star choices must be distinct Lix zero-based indexes 0..9')
    if type(budget) is not int or not 0<=budget<=1000000:
        raise ValueError('Explicit starlight budget required')
    return dict(choices=list(choices),budget=budget)


def apply(directory,source,task_plan,team_edit=None):
    path=directory/'user-mirror-starlight.json'
    if source not in ('saved','team','task','auto'):raise ValueError('Unknown star rule source')
    setting=None if source=='saved' else dict(version=1,source=source,task=plan(task_plan))
    profiles=ProfileStore(directory/'user-team-profiles.json')
    changed=None
    if team_edit is not None:
        slot=team_edit['slot'];p=plan(team_edit)
        teams=list(profiles.load())
        old=next((t for t in teams if t.slot==slot),None)
        if old is None:raise ValueError('Star editor must reference a saved team')
        new=replace(old,graces=tuple(str(n) for n in p['choices']),grace_budget=p['budget'])
        ledger=directory/'user-run-ledger.json'
        active=read_json(ledger).get('active') if ledger.exists() else None
        if active and active.get('team')==slot and old!=new:
            raise ValueError('Finish the active run before changing its star build')
        if old!=new:
            teams[teams.index(old)]=new;changed=teams
    # Validate all choices before writing either file; no controller input here.
    if changed is not None:profiles.save(changed)
    if setting is not None:write_json(path,setting)
    return setting


def resolve(directory,slot):
    path=directory/'user-mirror-starlight.json'
    if not path.exists():return None  # Preserve explicit legacy launch configuration.
    settings=read_json(path)
    if settings.get('version')!=1:raise ValueError('Unknown star rule version')
    task=plan(settings['task']);source=settings['source']
    if source not in ('team','task','auto'):raise ValueError('Unknown star rule source')
    if source=='task':selected=task
    else:
        team=next((t for t in ProfileStore(directory/'user-team-profiles.json').load() if t.slot==slot),None)
        if team is None:raise ValueError('Current star team is not saved')
        if any(len(g)!=1 for g in team.graces):raise ValueError('Enhanced stars are not supported by this native rule')
        if source=='team':selected=plan(dict(choices=[int(g) for g in team.graces],budget=team.grace_budget))
        else:
            selected=plan(dict(choices=[int(g) for g in team.graces] if team.graces else task['choices'],
                budget=min(task['budget'],team.grace_budget) if team.grace_budget is not None else task['budget']))
    return dict(graces=','.join(str(n+1) for n in selected['choices']),
                grace_budget=selected['budget'],grace_auto=source=='auto',star_source=source,team=slot)


def affordable(priorities,budget,available,costs):
    if len(priorities)>10 or len(set(priorities))!=len(priorities):raise ValueError('Distinct auto priorities required')
    if type(available) is not int or available<0:raise ValueError('Current available starlight required')
    if type(budget) is not int or budget<0:raise ValueError('Current budget required')
    limit=min(budget,available);result=[];spent=0
    for n in priorities:
        if type(n) is not int or not 1<=n<=10 or n in result:raise ValueError('Invalid auto priority')
        cost=costs[n-1]
        if type(cost) is not int or cost<=0:raise ValueError('Every candidate needs a current visible cost')
        if spent+cost<=limit:result.append(n);spent+=cost
    return result


def collect(get_node):
    source=get_node('MirrorStarSource')['attach']['source']
    def read(prefix):
        budget=get_node(prefix+'Budget')['attach']['budget']
        if not isinstance(budget,str) or not budget.isdecimal() or len(budget)>7:
            raise ValueError('Star budget must be decimal digits')
        values=[get_node(prefix+str(n))['attach']['selected'] for n in range(10)]
        if any(type(v) is not bool for v in values):raise ValueError('Explicit star selections required')
        return dict(choices=[n for n,v in enumerate(values) if v],budget=int(budget))
    task=read('MirrorTaskStar') if source!='saved' else None
    edit=None
    enabled=get_node('MirrorTeamStarEdit')['attach']['edit']
    if type(enabled) is not bool:raise ValueError('Explicit team star edit switch required')
    if enabled:
        edit=dict(slot=get_node('MirrorTeamStarSlot')['attach']['slot'],**read('MirrorTeamStar'))
    return source,task,edit
