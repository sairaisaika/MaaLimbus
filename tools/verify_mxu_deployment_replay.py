"""Resolve saved MXU choices into installed PI and replay with frozen Agent.

No game controller, GUI Start dispatch, live sinner identity or battle proof.
"""
import argparse
from dataclasses import replace
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
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,SINNERS,read_json
from maalimbus.deployment import DeploymentDraft
from maalimbus.jobs import wait_job,wait_task
from verify_deployment_replay import Replay


def resolve_choices(interface, task):
    """Select only active children, using exact stored case names."""
    spec=next((t for t in interface['task'] if t['name']==task['taskName']),None)
    if spec is None:raise ValueError('Saved task no longer exists in this interface')
    overrides={}
    def visit(name):
        value=task['optionValues'][name]
        if value['type']!='select':raise ValueError('Expected fixed select option')
        case=next((c for c in interface['option'][name]['cases'] if c['name']==value['caseName']),None)
        if case is None:raise ValueError('Unknown saved option case')
        for node,params in case.get('pipeline_override',{}).items():
            if node in overrides:raise ValueError('Unexpected overlapping PI nodes')
            overrides[node]=params
        for child in case.get('option',[]):visit(child)
    for name in spec['option']:visit(name)
    return overrides


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--expected-source',required=True)
    args=parser.parse_args();app=args.app.resolve()
    info=read_json(app/'build-info.json')
    assert not info['source_dirty'] and info['source_commit'].startswith(args.expected_source)
    config=read_json(app/'config/mxu-MaaLimbus.json')
    assert not config['settings']['autoRunOnLaunch']
    tasks=[t for i in config['instances'] for t in i['tasks']]
    assert len(tasks)==1 and not tasks[0]['enabled']
    selected=next((t for t in read_json(app/'interface.json')['task'] if t['name']==tasks[0]['taskName']),None)
    if selected is None or selected['entry']!='DeploymentStart':
        raise ValueError('This legacy deployment verifier requires its original diagnostic interface')
    patches=resolve_choices(read_json(app/'interface.json'),tasks[0])
    assert patches['DeploymentPreset']['custom_action_param']['preset']=='custom'
    draft=DeploymentDraft()
    for i in range(1,13):
        choice=patches[f'DeploymentOrder{i}']['custom_action_param']
        draft.choose(choice['position'],choice['sinner'])
    order=draft.finish()
    slot=patches['DeploymentConfigure']['custom_action_param']['slot']
    output=ROOT/'evidence/runtime'/('mxu-deployment-options-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    journal=output/'journal';journal.mkdir(parents=True)
    store=ProfileStore(output/'config/user-team-profiles.json')
    team=Team(slot,frozenset({'Burn'}),'Retained fixture team',deployment=SINNERS,pack_weights=(('ASEA',20),))
    other=Team(20 if slot!=20 else 19,frozenset({'Bleed'}),deployment=SINNERS)
    store.save([team,other])
    Library.open(app/'maafw',agent_server=False);Toolkit.init_option(ROOT/'build/mxu-options-replay-debug')
    resource,agent=Resource(),AgentClient();agent.set_timeout(5000);assert agent.bind(resource)
    controller=Replay('custom_choices',order[:3]);tasker=None
    env={**os.environ,'PI_RESOURCE':json.dumps({'name':'en'}),'MAALIMBUS_EVIDENCE':str(journal),
        'MAALIMBUS_DATA_PATH':str(store.path.parent)}
    with (output/'stdout.log').open('w') as out,(output/'stderr.log').open('w') as err:
        child=subprocess.Popen([str(app/'agent/MaaLimbusAgent.exe'),agent.identifier],cwd=output,
            env=env,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            assert agent.connect()
            for layer in ('base','en'):wait_job(resource.post_bundle(app/f'assets/resource/{layer}'),timeout=20)
            wait_job(controller.post_connection(),timeout=5);tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
            patches.update(DeploymentStart={'action':'DoNothing'},DeploymentNext={'timeout':1300,'post_delay':50})
            result=wait_task(tasker,tasker.post_task('DeploymentStart',patches),deadline=time.monotonic()+25)
            assert result['stop_confirmed'] and not result['timed_out']
            assert len(controller.clicks)==3 and tuple(c[0] for c in controller.clicks)==order[:3]
            assert store.load()==(replace(team,deployment=order),other)
            events=[json.loads(l) for l in (journal/'events.jsonl').read_text(encoding='utf-8').splitlines()]
            proof=[e for e in events if e['event']=='deployment_order_observed']
            assert len(proof)==1 and tuple(proof[0]['order'])==order[:3]
            assert not proof[0]['battle_started'] and not proof[0]['verified_clear']
        finally:
            if tasker is not None and tasker.running:wait_job(tasker.post_stop(),timeout=5)
            agent.disconnect()
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    record=dict(passed=True,source_commit=info['source_commit'],app=str(app),choices=tasks[0]['optionValues'],
        saved_order=order,clicks=controller.clicks,result=result,evidence=str(output),
        device_controller=False,gui_start_dispatch_verified=False,battle_started=False,verified_clear=False,
        scope='Actual saved MXU options resolved against installed PI; frozen Agent on derived deployment frames. No GUI task start, live geometry or clear.')
    (ROOT/'build/mxu-deployment-options-replay-verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
