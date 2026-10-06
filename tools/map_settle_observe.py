"""Settle-and-observe: poll a bounded number of times until the page is identified.

Read-only. Uses the same MapObserve pipeline node (scene identity only, never an
input) and records every observation plus frame hashes, so a transition like
`CONNECTING` is captured and the settled page is identified or reported unknown.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

from maa.controller import AdbController
from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus.adb_preflight import foreground
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus.adb_device import (build, discover, foreground_of, input_policy,
                                   names)
from recognition import Journal, LimbusRecognition, MapObservation

PIPELINE_DIR = ROOT / 'build/map-observe-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': ['LimbusUnknown'], 'on_error': ['LimbusUnknown'],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/map-observe.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def observe(tasker, deadline):
    job = tasker.post_task('MapObserve')
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def observations(directory):
    events = [json.loads(line) for line in
              (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    return [e for e in events if e['event'] == 'map_observed']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None,
                        help='optional adb path restricting discovery; omit to let '
                             'MaaToolkit search and supply the emulator config')
    parser.add_argument('--address', required=True)
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--interval', type=float, default=5.0)
    args = parser.parse_args()
    directory = ROOT / ('evidence/runtime/map-settle-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 60 + args.rounds * (args.interval + 20)
    result = dict(pid=os.getpid(), address=args.address, input_sent=False,
                  foreground_before=None, rounds=[])
    try:
        Library.open(args.binary, agent_server=False)
        device = discover(args.address, args.adb)
        result['foreground_before'] = foreground_of(device)
        Toolkit.init_option(prepare())
        controller = build(device, input_enabled=False)
        result['device'] = device
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        journal = Journal(directory)
        recognition = LimbusRecognition('en', journal)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', recognition)
        resource.register_custom_action('limbus_map_observe', MapObservation(recognition))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'), timeout=20, deadline=deadline)
        wait_job(resource.post_bundle(PIPELINE_DIR), timeout=20, deadline=deadline)
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)
        last = None
        for index in range(args.rounds):
            task = observe(tasker, deadline)
            observed = observations(directory)[-1]
            result['rounds'].append(dict(round=index + 1, task=task, observation=observed))
            last = observed
            if observed['scene'] not in ('UNKNOWN',):
                break
            if index + 1 < args.rounds:
                time.sleep(args.interval)
        result['settled_scene'] = None if last is None else last['scene']
        result['settled'] = last
        result['foreground_after'] = foreground_of(device)
        result['reason'] = 'bounded_settle_observation'
        result['passed'] = result['foreground_after'] == result['foreground_before']
    except Exception as error:
        result.update(reason='settle_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}, ensure_ascii=False, indent=1))
        print(json.dumps([r['observation'] for r in result['rounds']], ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
