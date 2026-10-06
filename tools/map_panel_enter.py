"""Click the node info panel's Enter action once, then record the successor page.

Same live-input gate as `tools/map_probe_one_node.py`: it refuses without the
nonce in `build/map-probe-authorization.json`, never picks its own target, never
clicks twice and never sends a key. It only clicks when the fresh page is an
identified node panel whose `Enter` action is present.
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
from maalimbus.adb_device import build, discover, input_policy, names
from maalimbus.vision import inset_box
from recognition import Journal, LimbusRecognition, MapObservation

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'
PIPELINE_DIR = ROOT / 'build/map-panel-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': ['LimbusUnknown'], 'on_error': ['LimbusUnknown'],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/map-panel.json').write_text(
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


def last_observation(journal_dir):
    events = [json.loads(line) for line in
              (journal_dir / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    observed = [e for e in events if e['event'] == 'map_observed']
    return observed[-1] if observed else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/map-panel-enter-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 180
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  clicks_sent=0, verified_clear=False,
                  foreground_before=foreground(args.adb, args.address))
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            print(json.dumps(result, ensure_ascii=False, indent=1))
            return 1
        device['input_policy'] = reason
        controller = build(device, input_enabled=True)
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

        result['before'] = run_observe(tasker, deadline)
        result['before_observation'] = last_observation(directory)
        if not result['before_observation'] or result['before_observation']['scene'] != 'NODE_PANEL':
            result.update(refused='page_is_not_an_identified_node_panel', passed=False)
            return 1

        # The observation already recorded the panel's Enter box; never re-derive a
        # target from anything but that fresh recognition.
        box_record = result['before_observation'].get('panel_enter_box')
        if not box_record:
            result.update(refused='node_panel_enter_not_present', passed=False)
            return 1
        box = tuple(box_record)
        panel_title = result['before_observation'].get('panel_title')
        x, y, w, h = inset_box(box, .25)
        target = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
        delay = random.randint(350, 750)
        journal.record('map_panel_enter_intent', enter_box=list(box), target=list(target),
                       panel_title=panel_title, delay_ms=delay, verified_clear=False)
        wait_job(controller.post_click(*target), timeout=10, deadline=deadline)
        result.update(clicks_sent=1, click_target=list(target), enter_box=list(box),
                      panel_title=panel_title, delay_ms=delay)
        time.sleep(delay / 1000)
        result['after'] = run_observe(tasker, deadline)
        result['after_observation'] = last_observation(directory)
        result['page_changed'] = bool(
            result['after_observation'] and result['before_observation']
            and result['after_observation']['frame'] != result['before_observation']['frame'])
        result['foreground_after'] = foreground(args.adb, args.address)
        result['reason'] = 'panel_enter_successor_recorded'
        result['passed'] = (result['clicks_sent'] == 1
                            and result['foreground_after'] == result['foreground_before'])
    except Exception as error:
        result.update(reason='map_panel_enter_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
