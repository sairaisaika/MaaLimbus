"""Production deployment graph through frozen Agent IPC; no game controller."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from maa.agent_client import AgentClient
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from verify_deployment_replay import Replay,ORDER
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,SINNERS
from maalimbus.jobs import wait_job,wait_task
from maalimbus.update_stage import verify_package


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--expected-source',required=True)
    args=parser.parse_args();app=args.app.resolve()
    files=verify_package(app)
    info=json.loads((app/'build-info.json').read_text(encoding='utf-8'))
    assert not info['source_dirty'] and info['source_commit'].startswith(args.expected_source)
    Library.open(app/'maafw',agent_server=False);Toolkit.init_option(ROOT/'build/packaged-deployment-debug')
    output=ROOT/'evidence/runtime'/('packaged-deployment-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    results=[]
    for case,expected,ready in [('ordered',3,True),('stuck',1,False),('paid',0,False),
            ('custom_choices',3,True),('duplicate_choices',0,False),('partial_choices',0,False),
            ('callback_json',0,False),('callback_profile',0,False),('callback_journal',0,False)]:
        evidence=output/case;journal=evidence/'journal';journal.mkdir(parents=True)
        store=ProfileStore(evidence/'config/user-team-profiles.json')
        team=Team(2,frozenset({'Burn'}),name='Retained team',deployment=ORDER,pack_weights=(('ASEA',20),))
        store.save([team]);resource,agent=Resource(),AgentClient();agent.set_timeout(5000);assert agent.bind(resource)
        custom_order=tuple(reversed(SINNERS))
        controller=Replay(case,custom_order[:3] if case=='custom_choices' else ORDER);tasker=None
        if case=='callback_profile':store.path.write_text('{',encoding='utf-8')
        env={**os.environ,'PI_RESOURCE':json.dumps({'name':'en'}),'MAALIMBUS_EVIDENCE':str(journal),'MAALIMBUS_DATA_PATH':str(store.path.parent)}
        with (evidence/'stdout.log').open('w') as out,(evidence/'stderr.log').open('w') as err:
            child=subprocess.Popen([str(app/'agent/MaaLimbusAgent.exe'),agent.identifier],cwd=evidence,
                env=env,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                assert agent.connect() and 'limbus_deployment_proof' in agent.custom_action_list
                for layer in ('base','en'):wait_job(resource.post_bundle(app/f'assets/resource/{layer}'),timeout=20)
                wait_job(controller.post_connection(),timeout=5);tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
                patches={'DeploymentStart':{'action':'DoNothing'},
                    'DeploymentConfigure':{'custom_action_param':{'mode':'configure','slot':2}},
                    'DeploymentPreset':{'timeout':1300},'DeploymentNext':{'post_delay':50,'timeout':1300}}
                if case in ('custom_choices','duplicate_choices','partial_choices'):
                    patches['DeploymentPreset']['custom_action_param']={'mode':'deployment','preset':'custom'}
                    for i,name in enumerate(custom_order,1):
                        patches[f'DeploymentOrder{i}']={'custom_action_param':{'mode':'deployment_slot',
                            'position':i,'sinner':custom_order[0] if case=='duplicate_choices' else name}}
                    if case=='partial_choices':patches['DeploymentOrder6']['action']='DoNothing'
                if case=='callback_json':patches['DeploymentPreset']['custom_action_param']='{'
                if case=='callback_journal':
                    # Agent startup has written pi_controller; fail later callback writes.
                    (journal/'events.jsonl').rename(journal/'startup-events.jsonl')
                    (journal/'events.jsonl').mkdir()
                result=wait_task(tasker,tasker.post_task('DeploymentStart',patches),deadline=time.monotonic()+25)
                assert result['stop_confirmed'] and not result['timed_out']
                assert len(controller.clicks)==expected
                if case=='callback_profile':assert store.path.read_text(encoding='utf-8')=='{'
                else:
                    saved=Team(team.slot,team.keywords,team.name,deployment=custom_order,
                        pack_weights=team.pack_weights) if case=='custom_choices' else team
                    assert store.load()==(saved,)
                events_path=journal/'events.jsonl'
                events=[json.loads(l) for l in events_path.read_text(encoding='utf-8').splitlines()] if events_path.is_file() else []
                if case in ('duplicate_choices','partial_choices','callback_json','callback_profile'):
                    assert any(e['event']=='callback_failed' for e in events)
                proof=[e for e in events if e['event']=='deployment_order_observed']
                assert bool(proof)==ready
                if ready:assert tuple(proof[-1]['order'])==(custom_order[:3] if case=='custom_choices' else ORDER)
                assert all(not p['battle_started'] and not p['verified_clear'] for p in proof)
                results.append(dict(case=case,clicks=controller.clicks,order_observed=ready,result=result))
            finally:
                if tasker is not None and tasker.running:wait_job(tasker.post_stop(),timeout=5)
                agent.disconnect()
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    result=dict(passed=True,app=str(app),files=files,source_commit=info['source_commit'],device_controller=False,battle_started=False,verified_clear=False,
        cases=results,evidence=str(output),scope='Frozen Agent IPC/installed production graph on derived counter/local OCR ordinal frames. No live geometry, identity, Japanese text or battle verification.')
    path=ROOT/'build/packaged-deployment-replay-verification.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
