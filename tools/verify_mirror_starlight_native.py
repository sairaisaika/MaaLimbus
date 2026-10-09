"""Native Maa option patches for Mirror star rules; no device/controller input."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.mirror_starlight import collect,apply,resolve
from maalimbus.storage import ProfileStore
from maalimbus.policies import Team


def main():
    pi=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf8'))
    Library.open(ROOT/'dist/MaaLimbus/maafw')
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=30)
    def choice(name,case):
        item=next(c for c in pi['option'][name]['cases'] if c['name']==case)
        assert resource.override_pipeline(item['pipeline_override'])
    choice('mirror_star_source','auto')
    patch=json.loads(json.dumps(pi['option']['mirror_star_task_budget']['pipeline_override']).replace('{budget}','100'))
    assert resource.override_pipeline(patch)
    for n in (1,3,4,6):choice(f'mirror_star_task_{n}','on')
    actual=collect(resource.get_node_data)
    assert actual==('auto',dict(choices=[1,3,4,6],budget=100),None)
    choice('mirror_star_team_editor','edit');choice('mirror_star_team_slot','2')
    patch=json.loads(json.dumps(pi['option']['mirror_star_team_budget']['pipeline_override']).replace('{budget}','75'))
    assert resource.override_pipeline(patch)
    for n in (0,5):choice(f'mirror_star_team_{n}','on')
    actual=collect(resource.get_node_data)
    assert actual[1]==dict(choices=[1,3,4,6],budget=100)
    assert actual[2]==dict(slot=2,choices=[0,5],budget=75)
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
        directory=Path(temporary)
        profiles=ProfileStore(directory/'user-team-profiles.json')
        profiles.save([Team(2,frozenset({'Charge'})),Team(7,frozenset({'Poise'}))])
        apply(directory,*actual)
        build=resolve(directory,2)
        assert build['graces']=='1,6' and build['grace_budget']==75 and build['grace_auto']
        fallback=resolve(directory,7)
        assert fallback['graces']=='2,4,5,7' and fallback['grace_budget']==100
    proof=dict(passed=True,native_options=actual,team2=build,team7=fallback,
        scope='actual native parsing/independent option patches and isolated saved-build resolution',
        device_controller=False,input_sent=False,live_star_selection_verified=False,gui_verified=False)
    (ROOT/'build/mirror-starlight-native-verification.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    print(json.dumps(proof))


if __name__=='__main__':main()
