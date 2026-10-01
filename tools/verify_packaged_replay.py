"""Exercise the packaged Agent over Maa IPC using saved frames, never game input."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np
from maa.agent_client import AgentClient
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from maalimbus.jobs import wait_job, wait_task
from verify_native_replay import Replay, redact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--references', type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    Library.open(app/'maafw', agent_server=False)
    Toolkit.init_option(ROOT/'build/packaged-replay-debug')
    originals = []
    for name,kind in [('image-3.png','drive'),('image-4.png','entry'),('image-2.png','team')]:
        frame = cv2.imread(str(args.references/name))
        if frame is None:
            raise RuntimeError(f'Missing reference: {name}')
        originals.append(redact(frame,kind))
    output = ROOT/'evidence/runtime'/('packaged-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    results = []
    for case in ('reference_navigation','unknown_zero_input'):
        evidence = output/case
        evidence.mkdir(parents=True)
        frames = originals if case=='reference_navigation' else [np.zeros_like(originals[0])]
        resource, controller, agent = Resource(), Replay(frames), AgentClient()
        agent.set_timeout(5000)
        assert agent.bind(resource)
        environment = {**os.environ, 'PI_RESOURCE':json.dumps({'name':'en'}),
                       'MAALIMBUS_EVIDENCE':str(evidence)}
        with (evidence/'agent.stdout.log').open('w') as stdout, (evidence/'agent.stderr.log').open('w') as stderr:
            child = subprocess.Popen([str(app/'agent/MaaLimbusAgent.exe'),agent.identifier],
                    cwd=output.parent,env=environment,stdout=stdout,stderr=stderr,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            tasker = None
            try:
                if not agent.connect():
                    raise RuntimeError('Packaged Agent IPC connection failed')
                assert 'limbus_scene' in agent.custom_recognition_list
                assert {'limbus_terminal','limbus_team','limbus_preflight'} <= set(agent.custom_action_list)
                for locale in ('base','en'):
                    wait_job(resource.post_bundle(app/f'assets/resource/{locale}'),timeout=20)
                wait_job(controller.post_connection(),timeout=5)
                tasker = Tasker()
                assert tasker.bind(resource=resource,controller=controller)
                override = {n:{'timeout':1500,'post_delay':50} for n in ('MirrorHard','MirrorDrive','MirrorEnter')}
                # Only the replay controller skips OS identity; no Win32 controller is constructed.
                override['MirrorHard']['action']='DoNothing'
                result = wait_task(tasker, tasker.post_task('MirrorHard',override),deadline=time.monotonic()+25)
                if not result['stop_confirmed'] or result['timed_out']:
                    raise RuntimeError('Packaged replay did not terminate within its budget')
                events = [json.loads(line) for line in (evidence/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                terminal = next(e for e in reversed(events) if e['event']=='terminal')
                expected = 'TEAM_LIBRARY' if case=='reference_navigation' else 'UNKNOWN'
                assert terminal['last_scene']==expected
                assert len(controller.clicks)==(2 if case=='reference_navigation' else 0)
                results.append({'case':case,'clicks':controller.clicks,'terminal':terminal,
                                'verified_clear':False,'result':result})
            finally:
                if tasker is not None and tasker.running:
                    wait_job(tasker.post_stop(),timeout=5)
                agent.disconnect()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
    record = {'passed':True,'app':str(app),'device_controller':False,'cases':results,
              'scope':'Packaged Agent IPC + installed resources + actual Maa OCR/Pipeline over saved frames; no live entry or dungeon clear.',
              'evidence':str(output)}
    (ROOT/'build/packaged-replay-verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
