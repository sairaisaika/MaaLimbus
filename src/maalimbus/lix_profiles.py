"""Import only explicit mirror/team preferences; never import Lix runtime/input."""
from dataclasses import replace
from .policies import Team
from .storage import KEYWORDS, SINNERS


def import_profiles(value, existing=()):
    slots=value.get('team_indexes')
    if not isinstance(slots,list) or not slots or len(slots)>20 or len(set(slots))!=len(slots):
        raise ValueError('Lix rotation must contain unique team slots')
    columns=('mirror_team_styles','mirror_team_ego_gift_styles','team_orders',
             'mirror_team_stars','mirror_team_initial_ego_orders',
             'mirror_team_ego_allow_list','mirror_team_ego_block_list')
    if any(not isinstance(value.get(k),list) or len(value[k])!=len(slots) for k in columns):
        raise ValueError('Lix profile columns do not match the rotation')
    previous={t.slot:t for t in existing}; result=[]
    for i,slot in enumerate(slots):
        if type(slot)is not int:raise ValueError('Team slot must be an integer')
        style=value['mirror_team_styles'][i]
        styles=frozenset(style.split('+')) if isinstance(style,str) else frozenset(style)
        gifts=frozenset(value['mirror_team_ego_gift_styles'][i])
        order=tuple(value['team_orders'][i])
        if not styles or not styles<=set(KEYWORDS) or not gifts<=set(KEYWORDS):
            raise ValueError('Unsupported Lix team/gift keyword')
        if len(order)!=12 or set(order)!=set(SINNERS):
            raise ValueError('Lix deployment must contain each sinner once')
        team=replace(previous.get(slot,Team(slot,frozenset())),keywords=gifts,
            formation_keywords=styles,deployment=order,graces=tuple(value['mirror_team_stars'][i]),
            initial_gifts=tuple(value['mirror_team_initial_ego_orders'][i]),
            allow=frozenset(value['mirror_team_ego_allow_list'][i]),
            block=frozenset(value['mirror_team_ego_block_list'][i]))
        result.append(team)
    result.extend(t for t in existing if t.slot not in slots)
    return tuple(result)
