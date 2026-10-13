"""Read visible loadout rows and search only inside the scrollable team sidebar."""
import re
from .vision import find
from .storage import read_json,write_json
TEAM=r'^\s*TEAMS\s*#\s*([1-9]|[1-3][0-9]|40)\s*$'

def sidebar_rows(records,size):
    return sorted(find(records,r'.+',(.045,.40,.15,.80),size,.9),key=lambda r:r.box[1])

def browse(records,size,wanted,state):
    rows=sidebar_rows(records,size)
    targets=[r for r in rows if re.fullmatch(TEAM,r.text,re.I)
             and int(re.fullmatch(TEAM,r.text,re.I).group(1))==wanted]
    if len(targets)==1:return dict(target=list(targets[0].box),rows=[r.text for r in rows])
    if type(wanted) is not int or not 1<=wanted<=40:return dict(reason='saved_team_slot_invalid')
    signature=tuple(r.text.strip() for r in rows)
    if not signature:return dict(reason='team_sidebar_rows_not_read')
    nums=[int(m.group(1)) for r in rows if (m:=re.fullmatch(TEAM,r.text,re.I))]
    if 'direction' not in state:state['direction']='up' if nums and wanted<min(nums) else 'down'
    if state.get('last_rows')==list(signature):state['unchanged']=state.get('unchanged',0)+1
    else:state['unchanged']=0
    if state.get('unchanged',0)>=2:
        if state.get('reversed'):return dict(reason='team_list_search_stalled',rows=list(signature))
        state.update(direction='down' if state['direction']=='up' else 'up',reversed=True,unchanged=0)
    if state.get('attempts',0)>=12:return dict(reason='team_list_search_budget_exhausted',rows=list(signature))
    state.update(attempts=state.get('attempts',0)+1,last_rows=list(signature))
    sx,sy=size[0]/1920,size[1]/1080
    y1,y2=(716,488) if state['direction']=='down' else (488,716)
    return dict(rows=list(signature),direction=state['direction'],attempt=state['attempts'],
                start=[round(185*sx-12),round(y1*sy-12),24,24],to=[round(185*sx),round(y2*sy)])

def prepare(path,scope,records,size,wanted):
    data=read_json(path) if path.exists() else {}
    if data.get('scope')!=scope or data.get('wanted')!=wanted:data=dict(scope=scope,wanted=wanted)
    result=browse(records,size,wanted,data)
    if result.get('start'):write_json(path,data)
    return result
