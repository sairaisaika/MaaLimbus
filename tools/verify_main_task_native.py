"""Read six actual Maa resource entries and independent saved-team option patches."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.mirror_task_options import collect


def main():
    pi=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource()
    wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=30)
    routes={t['name']:resource.get_node_data(t['entry'])['action']['param']['custom_action_param']['task'] for t in pi['task']}
    assert list(routes)==['open_game','mirror_loop','experience','thread','rewards','stamina']
    assert routes['mirror_loop']=='mirror'
    for option,slot in (('experience_team',7),('thread_team',2)):
        selected=next(c for c in pi['option'][option]['cases'] if c['name']==str(slot))
        assert resource.override_pipeline(selected['pipeline_override'])
    assert resource.get_node_data('LuxExperienceTeam')['attach']['slot']==7
    assert resource.get_node_data('LuxThreadTeam')['attach']['slot']==2
    # Independent overrides must not erase or replace each other.
    assert resource.get_node_data('ExperienceTask')['action']['param']['custom_action_param']['task']=='experience'
    assert collect(resource.get_node_data)=={}
    for option,case in [('mirror_initial_keyword','poise'),('mirror_gift_search','refuse'),('mirror_run_bounds','120')]:
        selected=next(c for c in pi['option'][option]['cases'] if c['name']==case)
        assert resource.override_pipeline(selected['pipeline_override'])
    task_settings=collect(resource.get_node_data)
    assert task_settings==dict(gift_keyword='poise',gift_search='refuse',steps=120)
    assert resource.get_node_data('MirrorStarSource')['attach']['source']=='saved'
    proof=dict(passed=True,routes=routes,experience_team=7,thread_team=2,mirror_task_settings=task_settings,
               device_controller=False,input_sent=False,gui_dispatch_verified=False,
               scope='actual native resource parsing and independent options; no game completion claim')
    (ROOT/'build/six-task-native-verification.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof))


if __name__=='__main__':main()
