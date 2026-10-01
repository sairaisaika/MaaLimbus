"""Frozen Agent battle-planning IPC on derived frames, without a game controller."""
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
from verify_battle_plan_replay import Replay
from maalimbus.jobs import wait_job,wait_task
from maalimbus.update_stage import verify_package


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True)
    args=parser.parse_args();app=args.app.resolve()
    files=verify_package(app)
    info=json.loads((app/'build-info.json').read_text(encoding='utf-8'))
    assert not info['source_dirty'] and info['source_commit'].startswith('8b309b8')
    Library.open(app/'maafw',agent_server=False);Toolkit.init_option(ROOT/'build/packaged-battle-debug')
    output=ROOT/'evidence/runtime'/('packaged-battle-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    results=[]
    for case in ('plan','stuck','paid','jp'):
        evidence=output/case;journal=evidence/'journal';journal.mkdir(parents=True)
        resource,agent=Resource(),AgentClient();agent.set_timeout(5000);assert agent.bind(resource)
        controller=Replay(case);tasker=None
        env={**os.environ,'PI_RESOURCE':json.dumps({'name':'jp' if case=='jp' else 'en'}),
             'MAALIMBUS_EVIDENCE':str(journal),'MAALIMBUS_DATA_PATH':str(evidence/'config')}
        with (evidence/'stdout.log').open('w') as out,(evidence/'stderr.log').open('w') as err:
            child=subprocess.Popen([str(app/'agent/MaaLimbusAgent.exe'),agent.identifier],cwd=evidence,
                env=env,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                assert agent.connect() and 'limbus_battle_plan_observe' in agent.custom_action_list
                for layer in ('base','jp' if case=='jp' else 'en'):
                    wait_job(resource.post_bundle(app/f'assets/resource/{layer}'),timeout=20)
                wait_job(controller.post_connection(),timeout=5);tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
                patches={'BattlePlanStart':{'action':'DoNothing','timeout':900},
                         'BattlePlanOnce':{'post_delay':50,'timeout':900}}
                result=wait_task(tasker,tasker.post_task('BattlePlanStart',patches),deadline=time.monotonic()+20)
                assert result['stop_confirmed'] and not result['timed_out']
                assert controller.keys==([80] if case in ('plan','stuck') else [])
                events=[json.loads(l) for l in (journal/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                proof=[e for e in events if e['event']=='battle_plan_observed']
                if case in ('plan','stuck'):
                    assert len(proof)==1 and proof[0]['frame_changed']==(case=='plan')
                    assert not proof[0]['turn_submitted'] and not proof[0]['verified_clear']
                    if case=='plan':assert any(p['label']=='neutral' and p['attention'] for p in proof[0]['labels'])
                else:assert not proof
                results.append({'case':case,'keys':controller.keys,'result':result,'observations':proof})
            finally:
                if tasker is not None and tasker.running:wait_job(tasker.post_stop(),timeout=5)
                agent.disconnect()
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    integrity={'passed':True,'files':files,'source_commit':info['source_commit'],'source_dirty':False,
               'private_roots_excluded':True,'verified_clear':False,'app':str(app)}
    (ROOT/'build/battle-package-integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
    result={'passed':True,'app':str(app),'files':files,'source_commit':info['source_commit'],
        'cases':results,'evidence':str(output),'device_controller':False,'turn_submitted':False,
        'verified_clear':False,'scope':'Actual frozen Agent IPC/installed graph; derived English glyph/diagnostic frames, no live input or Japanese UI proof'}
    (ROOT/'build/packaged-battle-replay-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'files':files,'cases':len(results),'key_presses':[len(r['keys']) for r in results],'app':str(app)}))


if __name__=='__main__':main()
