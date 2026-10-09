"""Explicit Mirror-owned editors update saved preferences, never the roster."""
from dataclasses import replace
from .storage import ProfileStore, read_json


def collect(get_node):
    enabled=get_node('MirrorPreferenceEdit')['attach']['enabled']
    if type(enabled) is not bool:raise ValueError('Explicit preference edit switch required')
    if not enabled:return None
    return dict(slot=get_node('MirrorPreferenceSlot')['attach']['slot'],
        allow=get_node('MirrorPreferenceAllow')['attach']['name'],
        block=get_node('MirrorPreferenceBlock')['attach']['name'],
        preferred=get_node('MirrorPreferencePack')['attach']['name'],
        avoided=get_node('MirrorPreferenceAvoidPack')['attach']['name'],
        weight=get_node('MirrorPreferenceWeight')['attach']['weight'])


def apply(directory, edit, *, gifts, packs):
    if edit is None:return None
    slot=edit['slot']
    if type(slot) is not int or not 1<=slot<=20:raise ValueError('Unknown saved team')
    for key,catalog in [('allow',gifts),('block',gifts),('preferred',packs),('avoided',packs)]:
        if edit[key]!='saved' and edit[key] not in catalog:
            raise ValueError('Unknown preference catalog identity')
    weight=edit['weight']
    if type(weight) is not int or not 1<=weight<=100:raise ValueError('Theme weight must be 1..100')
    if edit['preferred']!='saved' and edit['preferred']==edit['avoided']:
        raise ValueError('A theme cannot be preferred and blocked together')
    store=ProfileStore(directory/'user-team-profiles.json')
    teams=list(store.load())
    team=next((p for p in teams if p.slot==slot),None)
    if team is None:raise ValueError('Saved team missing')
    allow=set(team.allow);block=set(team.block);weights=dict(team.pack_weights)
    if edit['allow']!='saved':allow.add(edit['allow'])
    if edit['block']!='saved':block.add(edit['block'])
    if edit['preferred']!='saved':weights[edit['preferred']]=weight
    if edit['avoided']!='saved':weights[edit['avoided']]=0
    # Blocks always win in the existing runtime ranking. Do not delete prior
    # lists or change formation/system/starlight metadata as a side effect.
    revised=replace(team,allow=frozenset(allow),block=frozenset(block),pack_weights=tuple(weights.items()))
    ledger_path=directory/'user-run-ledger.json'
    if ledger_path.exists():
        ledger=read_json(ledger_path)
        if ledger.get('version')!=1:raise ValueError('Invalid run ledger')
        active=ledger.get('active')
        if active is not None and (not isinstance(active,dict) or
                type(active.get('team')) is not int or not 1<=active['team']<=20 or
                not isinstance(active.get('id'),str) or not active['id']):
            raise ValueError('Invalid active run ledger')
        if active and active.get('team')==slot and revised!=team:
            raise ValueError('Finish the active team run before editing its preferences')
    if revised!=team:
        store.save([revised if p.slot==slot else p for p in teams])
    return revised
