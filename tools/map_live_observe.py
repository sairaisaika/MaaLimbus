"""Read-only MuMu verification of the map page identity and bounded route refusal.

Connects an Android controller with the Null input method, checks that Limbus is
the unique foreground app, captures one frame and runs the real Maa pipeline node
`MapObserve` (limbus_map_observe). No click, swipe or key is ever sent.
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
from maalimbus.adb_device import build, discover, input_policy, names
from maalimbus.map_vision import map_header, route_decision
from maalimbus.vision import Text
from recognition import Journal, LimbusRecognition, MapObservation

PIPELINE_DIR = ROOT / 'build/map-live-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'Custom', 'custom_recognition': 'limbus_scene',
        'custom_recognition_param': {'scene': 'MAP'},
        'action': 'Custom', 'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/map-live.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--address', required=True)
    args = parser.parse_args()
    directory = ROOT / ('evidence/runtime/map-live-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  input_method='Null', input_sent=False, verified_clear=False,
                  foreground_before=foreground(args.adb, args.address))
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        controller = build(device, input_enabled=False)
        result['device'] = device
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        wait_job(controller.post_screencap(), timeout=15, deadline=deadline)
        frame = controller.cached_image
        if frame is None or not frame.size:
            raise RuntimeError('Maa screenshot unavailable')
        if not cv2.imwrite(str(directory / 'frame.png'), frame):
            raise RuntimeError('Frame could not be saved')
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
        job = tasker.post_task('MapObserve')
        try:
            task = wait_task(tasker, job, deadline=deadline)
            result.update(task_result=task, stop_confirmed=task['stop_confirmed'])
        except RuntimeError as error:
            # A page that is not an identified map stops the read-only node. The
            # observation event written before that stop is the actual evidence.
            if not job.done:
                wait_job(tasker.post_stop(), timeout=5)
            result.update(task_result={'task_succeeded': False, 'stop_confirmed': job.done,
                                       'error': str(error)}, stop_confirmed=job.done)
        result['input_sent'] = False
        events = [json.loads(line) for line in
                  (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        observed = next((e for e in events if e['event'] == 'map_observed'), None)
        frames = sorted(directory.glob('frame-*.json'))
        record = json.loads(frames[-1].read_text(encoding='utf-8')) if frames else {}
        result['scene'] = record.get('scene')
        if observed is not None:
            result['map_observed'] = observed
            result['route'] = observed['route']
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in record.get('ocr', [])]
        header = map_header(records, tuple(record['size'])) if record else None
        result['identity'] = None if header is None else {
            'floor': header.floor, 'pack': header.pack,
            'header_box': header.exploring_text.box, 'pack_box': header.pack_text.box}
        result['route_recheck'] = route_decision(header, tuple(record['size'])) if record else None
        result['foreground_after'] = foreground(args.adb, args.address)
        result['reason'] = ('read_only_map_observed' if result['scene'] == 'MAP'
                            else 'read_only_frame_is_not_an_identified_map')
        result['passed'] = bool(result['scene'] == 'MAP' and result.get('identity')
                                and observed is not None
                                and observed['route']['next_node'] is None
                                and result['route_recheck']['next_node'] is None
                                and not result['input_sent'])
    except Exception as error:
        result.update(reason='map_live_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                               encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
