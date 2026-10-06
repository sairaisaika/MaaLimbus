"""Initial gift page recognition from controls and keyword headers."""
import re
import hashlib
from pathlib import Path
import cv2
from .vision import Text, find, inset_box
from .storage import read_json


def counter(records,size):
    matches=find(records,r'^\s*(?:Select\s*)?\d\s*/\s*[1-3]\s*$',(.85,.76,.93,.86),size,.85)
    if len(matches)!=1:return None
    numbers=tuple(map(int,re.findall(r'\d',matches[0].text)))
    return numbers if numbers[0]<=numbers[1] else None


def page(records,size,locale):
    return (counter(records,size) is not None
        and len(find(records,locale.get('initial_selected',r'(?!)'),(.60,.19,.80,.26),size,.85))==1
        and len(find(records,locale.get('initial_refuse',r'(?!)'),(.61,.76,.77,.86),size,.85))==1
        and all(find(records,'^'+k+'$',(.12,.48,.57,.54),size,.85) for k in ('Sinking','Poise','Charge')))


def group_target(records,size,keyword):
    if keyword not in ('Burn','Bleed','Tremor','Rupture','Sinking','Poise','Charge','Slash'):return None
    matches=find(records,'^'+re.escape(keyword)+'$',(.12,.21,.57,.54),size,.85)
    return inset_box(matches[0].box) if len(matches)==1 else None


def row_target(records,size,ordinal):
    if ordinal not in (1,2,3):return None
    top=(322+160*(ordinal-1))/1080
    titles=find(records,r'.+',(.675,top+.015,.92,top+.046),size,.85)
    if len(titles)!=1:return None
    return inset_box(titles[0].box),titles[0].text


def selected_rows(image):
    if image.shape[:2]!=(1080,1920):return None
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    selected=[]
    for ordinal in (1,2,3):
        top=322+160*(ordinal-1)
        fraction=float((gray[top:top+11,1185:1728]>140).mean())
        if fraction>=.25:selected.append(ordinal)
        elif fraction>.10:return None
    return selected


def receipt_name(records,size):
    names=find(records,r'.+',(.255,.55,.39,.70),size,.85)
    names.sort(key=lambda r:(r.box[1],r.box[0]))
    return ' '.join(r.text for r in names) if names else None


def same_name(first,second):
    def normalized(value):return ''.join(c.casefold() for c in value if c.isalnum())
    return bool(first and second and normalized(first)==normalized(second))


def proven_titles(progress,evidence_root):
    frame=Path(progress['proof']).resolve()
    if not frame.is_relative_to(Path(evidence_root).resolve()):
        raise ValueError('Initial gift proof must be retained application evidence')
    source=read_json(frame.with_suffix('.json'))
    if source['image_sha256']!=hashlib.sha256(frame.read_bytes()).hexdigest():
        raise ValueError('Initial gift proof image changed')
    if source['scene']!='INITIAL_GIFTS':raise ValueError('Wrong proof scene')
    records=[Text(r['text'],tuple(r['box']),r['score']) for r in source['ocr']]
    titles=[row_target(records,source['size'],i) for i in progress['selected']]
    if any(t is None for t in titles):raise ValueError('Initial gift proof titles incomplete')
    return [t[1] for t in titles]
