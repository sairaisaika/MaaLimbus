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
from maalimbus.storage import ProfileStore
from maalimbus.jobs import wait_job,wait_task


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True)
    args=parser.parse_args();app=args.app.resolve()
    Library.open(app/'maafw',agent_server=False);Toolkit.init_option(ROOT/'build/packaged-deployment-debug')
    output=ROOT/'evidence/runtime'/('packaged-deployment-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    results=[]
    for case,expected,ready in [('ordered',3,True),('stuck',1,False),('paid',0,False)]:
        evidence=output/case;journal=evidence/'journal';journal.mkdir(parents=True)
        store=ProfileStore(evidence/'config/user-team-profiles.json')
        team=Team(2,frozenset({'Burn'}),name='Retained team',deployment=ORDER,pack_weights=(('ASEA',20),))
        store.save([team]);resource,agent=Resource(),AgentClient();agent.set_timeout(5000);assert agent.bind(resource)
        controller=Replay(case);tasker=None
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
                result=wait_task(tasker,tasker.post_task('DeploymentStart',patches),deadline=time.monotonic()+25)
                assert result['stop_confirmed'] and not result['timed_out']
                assert len(controller.clicks)==expected and store.load()==(team,)
                events=[json.loads(l) for l in (journal/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                proof=[e for e in events if e['event']=='deployment_order_observed']
                assert bool(proof)==ready
                if ready:assert tuple(proof[-1]['order'])==ORDER
                assert all(not p['battle_started'] and not p['verified_clear'] for p in proof)
                results.append(dict(case=case,clicks=controller.clicks,order_observed=ready,result=result))
            finally:
                if tasker is not None and tasker.running:wait_job(tasker.post_stop(),timeout=5)
                agent.disconnect()
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    result=dict(passed=True,app=str(app),device_controller=False,battle_started=False,verified_clear=False,
        cases=results,evidence=str(output),scope='Frozen Agent IPC/installed production graph on derived counter/local OCR ordinal frames. No live geometry, identity, Japanese text or battle verification.')
    path=ROOT/'build/packaged-deployment-replay-verification.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
