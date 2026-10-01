"""Frozen Agent IPC/production theme graph, no Win32 controller or game input."""
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
from verify_theme_replay import Replay,derived_frame
from maalimbus.theme_vision import ThemeCatalog
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore
from maalimbus.jobs import wait_job,wait_task


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True)
    args=parser.parse_args();app=args.app.resolve()
    Library.open(app/'maafw',agent_server=False)
    Toolkit.init_option(ROOT/'build/packaged-theme-debug')
    catalog=ThemeCatalog(app/'assets/resource/base')
    output=ROOT/'evidence/runtime'/('packaged-theme-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    results=[]
    for case,locale,target,options in [('weighted','en','ASEA',{}),('paid','en',None,{'paid':True})]:
        evidence=output/case;journal_dir=evidence/'journal';journal_dir.mkdir(parents=True)
        store=ProfileStore(evidence/'config/user-team-profiles.json')
        store.save([Team(2,frozenset(),name='Retained team',pack_weights=(('ASEA',5),('Automated Factory',1)))])
        resource,agent=Resource(),AgentClient();agent.set_timeout(5000);assert agent.bind(resource)
        controller=Replay(derived_frame(catalog,**options),target)
        env={**os.environ,'PI_RESOURCE':json.dumps({'name':locale}),
             'MAALIMBUS_EVIDENCE':str(journal_dir),'MAALIMBUS_DATA_PATH':str(store.path.parent)}
        tasker=None
        with (evidence/'stdout.log').open('w') as out,(evidence/'stderr.log').open('w') as err:
            child=subprocess.Popen([str(app/'agent/MaaLimbusAgent.exe'),agent.identifier],
                cwd=evidence,env=env,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                assert agent.connect()
                assert 'limbus_theme_observe' in agent.custom_action_list
                for layer in ('base',locale):wait_job(resource.post_bundle(app/f'assets/resource/{layer}'),timeout=20)
                wait_job(controller.post_connection(),timeout=5)
                tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
                patches={'ThemePackStart':{'action':'DoNothing'},
                    'ThemePackConfigure':{'custom_action_param':{'mode':'configure','slot':2},'timeout':1200},
                    'ThemePackPreference':{'custom_action_param':{'mode':'pack','name':'ASEA'}},
                    'ThemePackWeight':{'custom_action_param':{'mode':'weight','weight':20}},
                    'ThemePackDrag':{'post_delay':50}}
                result=wait_task(tasker,tasker.post_task('ThemePackStart',patches),deadline=time.monotonic()+25)
                assert result['stop_confirmed'] and not result['timed_out']
                assert len(controller.drags)==(1 if target else 0)
                assert store.load()==(Team(2,frozenset(),name='Retained team',pack_weights=(('ASEA',20),('Automated Factory',1))),)
                events=[json.loads(l) for l in (journal_dir/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                terminal=next(e for e in reversed(events) if e['event']=='terminal')
                assert terminal['reason']==('theme_drag_recorded_map_verification_pending' if target else 'unconfigured_resource_dialog')
                results.append(dict(case=case,locale=locale,drags=controller.drags,result=result,terminal=terminal))
            finally:
                if tasker is not None and tasker.running:wait_job(tasker.post_stop(),timeout=5)
                agent.disconnect()
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    record=dict(passed=True,app=str(app),device_controller=False,verified_clear=False,cases=results,
        evidence=str(output),scope='Frozen Agent IPC, installed theme assets and production graph, saved team 2 preference retained. Derived English glyph/title frames; no live/JP text/map proof.')
    path=ROOT/'build/packaged-theme-replay-verification.json';path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
