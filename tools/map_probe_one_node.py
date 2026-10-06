"""One-node map probe. Refuses to run without an explicit live authorisation.

This is the only MaaLimbus tool that can click on the map. It requires ALL of:

  * `--authorize <nonce>` equal to the nonce in `build/map-probe-authorization.json`
    (which you create), so no session can click by accident or by replaying an old
    command line;
  * `--allow-node <x> <y>` naming the exact normalized target, sampled inside an
    inset box with a bounded delay like every other input in this project;
  * Limbus uniquely in the foreground on the exact Android serial.

It observes the page, sends exactly one click, observes the successor page, and
stops. It never chooses a node itself, never clicks twice and never sends a key.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

import cv2
from maa.controller import AdbController
from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus.adb_preflight import foreground
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus.vision import inset_box
from recognition import Journal, LimbusRecognition, MapObservation

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'
PIPELINE_DIR = ROOT / 'build/map-probe-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': ['LimbusUnknown'], 'on_error': ['LimbusUnknown'],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/map-probe.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


def run_observe(tasker, deadline):
    job = tasker.post_task('MapObserve')
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--allow-node', nargs=2, type=int, required=True, metavar=('X', 'Y'),
                        help='normalized target inside an observed node, e.g. 1005 465')
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'create {AUTHORIZATION} containing '
                                  '{"live_input_authorized": true, "nonce": "<value>", '
                                  '"reason": "<why>"} and pass the same nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/map-probe-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 180
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  requested_node=list(args.allow_node), clicks_sent=0, verified_clear=False,
                  foreground_before=foreground(args.adb, args.address))
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        controller = AdbController(args.adb, args.address, MaaAdbScreencapMethodEnum.Encode,
                                   MaaAdbInputMethodEnum.Maatouch)
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

        before = run_observe(tasker, deadline)
        events = [json.loads(line) for line in
                  (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        pre = [e for e in events if e['event'] == 'map_observed']
        result['before'] = before
        result['before_observation'] = pre[-1] if pre else None
        if not pre or pre[-1]['scene'] != 'MAP':
            result.update(refused='page_is_not_an_identified_map_before_input', passed=False)
            return 1

        x_requested, y_requested = args.allow_node
        box = (x_requested - 30, y_requested - 30, 60, 60)
        ix, iy, iw, ih = inset_box(box, .25)
        target = (random.randint(ix, ix + max(1, iw)), random.randint(iy, iy + max(1, ih)))
        delay = random.randint(350, 750)
        journal.record('map_probe_intent', requested=list(args.allow_node), target=list(target),
                       box=list(box), delay_ms=delay, verified_clear=False)
        wait_job(controller.post_click(*target), timeout=10, deadline=deadline)
        result['clicks_sent'] = 1
        result['click_target'] = list(target)
        result['delay_ms'] = delay
        time.sleep(delay / 1000)
        after = run_observe(tasker, deadline)
        events = [json.loads(line) for line in
                  (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        post = [e for e in events if e['event'] == 'map_observed']
        result['after'] = after
        result['after_observation'] = post[-1] if post else None
        before_frames = sorted(directory.glob('frame-*.json'))
        result['evidence_frames'] = [p.name for p in before_frames]
        result['page_changed'] = bool(len(post) >= 2 and post[-1]['frame'] != post[0]['frame'])
        for name in ('frame-0001.png', 'frame-0002.png', 'frame-0003.png'):
            path = directory / name
            if path.is_file():
                image = cv2.imread(str(path))
                result.setdefault('frame_files', {})[name] = None if image is None else list(image.shape)
        result['foreground_after'] = foreground(args.adb, args.address)
        result['reason'] = 'single_click_successor_recorded'
        result['passed'] = (result['clicks_sent'] == 1
                            and result['foreground_after'] == result['foreground_before'])
    except Exception as error:
        result.update(reason='map_probe_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
