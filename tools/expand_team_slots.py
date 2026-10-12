"""Extend existing native independent team options to the game's forty slots."""
import json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def replace(value,slot,numbers=True):
    if isinstance(value,str):
        return value.replace('global_team_20',f'global_team_{slot}').replace('mirror_queue_20',f'mirror_queue_{slot}').replace('MirrorTaskQueue20',f'MirrorTaskQueue{slot}')
    if isinstance(value,list):return [replace(x,slot,numbers) for x in value]
    if isinstance(value,dict):return {replace(k,slot):slot if numbers and k in ('slot','count') and v==20 else replace(v,slot,numbers) for k,v in value.items()}
    return value


def expand(pi,nodes):
    pi=deepcopy(pi);nodes=deepcopy(nodes)
    old_options={k:v for k,v in pi['option'].items() if k=='global_team_20' or k.startswith('global_team_20_')}
    old_nodes={k:v for k,v in nodes.items() if k=='Global_global_team_20' or k.startswith('Global_global_team_20_')}
    section=next(s for s in pi['setting'] if s['name']=='global_team_20')
    for slot in range(21,41):
        for key,value in old_options.items():pi['option'][replace(key,slot)]=replace(value,slot)
        for key,value in old_nodes.items():nodes[replace(key,slot)]=replace(value,slot)
        name=f'global_team_{slot}'
        if name not in pi['global_option']:pi['global_option'].append(name)
        if not any(s['name']==name for s in pi['setting']):pi['setting'].append(replace(section,slot))
        next(s for s in pi['setting'] if s['name']==name)['label']=f'Team {slot}'
        pi['option'][f'mirror_queue_{slot}']=replace(pi['option']['mirror_queue_20'],slot,False)
        nodes[f'MirrorTaskQueue{slot}']=replace(nodes['MirrorTaskQueue20'],slot,False)
    for key in ('team_slot','run_team','team_build_slot','mirror_single_team','experience_team','thread_team',
                *(f'mirror_queue_{n}' for n in range(1,41))):
        cases=pi['option'][key]['cases'];template=next(c for c in cases if c['name']=='20')
        def select(value,slot):
            if isinstance(value,list):return [select(v,slot) for v in value]
            if isinstance(value,dict):return {k:slot if k=='slot' else select(v,slot) for k,v in value.items()}
            return value
        pi['option'][key]['cases']=[]
        for slot in range(1,41):
            case=select(deepcopy(template),slot);case['name']=str(slot);case['label']=str(slot)
            pi['option'][key]['cases'].append(case)
    cases=pi['option']['mirror_queue_count']['cases'];template=next(c for c in cases if c['name']=='20')
    for count in range(21,41):
        if any(c['name']==str(count) for c in cases):continue
        case=replace(template,count);case['name']=str(count);case['label']=str(count)
        case['option']=[f'mirror_queue_{n}' for n in range(1,count+1)];cases.append(case)
    return pi,nodes


if __name__=='__main__':
    paths=[ROOT/'assets/interface.json',ROOT/'assets/resource/base/pipeline/mirror.json']
    values=expand(*(json.loads(p.read_text(encoding='utf-8')) for p in paths))
    for path,value in zip(paths,values):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
