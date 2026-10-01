"""Evidence-based deployment order, using pinned LALC's 12 fixed grid slots.

The 0/1 fallback and blind reset/confirm behavior are deliberately not reused.
Counts and local order badges must agree before any next click. Geometry/badge
recognition is experimental until checked against a real deployment frame.
"""
from dataclasses import dataclass
import re

from .storage import SINNERS
from .vision import find,inset_box

CENTERS={name:(290+130*(index%6),240+200*(index//6)) for index,name in enumerate(SINNERS)}


@dataclass(frozen=True)
class DeploymentState:
    selected: int
    capacity: int
    order: tuple[str,...]


def counts(records,size):
    matches=find(records,r'^\s*\d{1,2}\s*/\s*\d{1,2}\s*$',(.882,.69,.966,.77),size,.85)
    if len(matches)!=1:return None
    selected,capacity=map(int,re.findall(r'\d+',matches[0].text))
    if not 1<=capacity<=12 or not 0<=selected<=capacity:return None
    return selected,capacity


def deployment_page(records,locale,size):
    return (counts(records,size) is not None
            and len(find(records,locale['details'],(.05,.02,.98,.30),size,.8))==1
            and abs(size[0]/size[1]-16/9)<.02)


def observe_deployment(records,size):
    counter=counts(records,size)
    if counter is None:return None
    selected,capacity=counter;w,h=size
    if abs(w/h-16/9)>=.02:return None
    badges={}
    for name,(cx,cy) in CENTERS.items():
        roi=((cx-52)/1280,(cy-88)/720,(cx+52)/1280,(cy-30)/720)
        matches=find(records,r'^\s*(?:[1-9]|1[0-2])\s*$',roi,size,.85)
        if len(matches)>1:return None
        if matches:
            ordinal=int(matches[0].text)
            if ordinal in badges:return None
            badges[ordinal]=name
    if set(badges)!=set(range(1,selected+1)):return None
    return DeploymentState(selected,capacity,tuple(badges[n] for n in range(1,selected+1)))


def badge_rois(size):
    scale=size[0]/1280
    return {name:tuple(round(v*scale) for v in (cx-25,cy-85,50,52))
            for name,(cx,cy) in CENTERS.items()}


def next_sinner(state,team):
    if state is None or len(team.deployment)<state.capacity:
        return 'stop',None
    expected=team.deployment[:state.capacity]
    if state.order!=expected[:state.selected]:return 'stop',None
    if state.selected==state.capacity:return 'complete',None
    return 'select',expected[state.selected]


def target_box(name,size):
    cx,cy=CENTERS[name];scale=size[0]/1280
    return inset_box(tuple(round(v*scale) for v in (cx-18,cy-18,36,36)))
