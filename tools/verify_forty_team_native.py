"""Verify actual native slot22/40 overrides without creating a controller."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.storage import write_json

if __name__=='__main__':
    pi=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=30)
    proofs=[]
    for position in (1,22,40):
        for selected in (22,40):
            case=next(c for c in pi['option'][f'mirror_queue_{position}']['cases'] if c['name']==str(selected))
            assert resource.override_pipeline(case['pipeline_override'])
            actual=resource.get_node_data(f'MirrorTaskQueue{position}')['attach']['slot']
            assert actual==selected;proofs.append(dict(position=position,selected=actual))
    for slot in (22,40):
        node=resource.get_node_data(f'Global_global_team_{slot}')
        assert node['attach']['global_build']['edit'] is False
    write_json(ROOT/'build/team40-native-verification.json',dict(passed=True,proofs=proofs,
        controller_created=False,input_sent=False,installed_gui_updated=False))
    print('Native 22/40 independent slot patches passed; zero controller/input')
