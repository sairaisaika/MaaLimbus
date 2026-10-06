"""One bounded map step: click a visible node and verify its info panel opens.

Same live-input gate as the other probes. It only acts on an identified map page,
clicks exactly once inside a node box read from that page, samples the point inside
an inset with a bounded delay, and requires the node info panel as the postcondition.
A click that opens no panel is recorded as a failure and never repeated.
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

from maalimbus.adb_device import build, discover, foreground_of, input_policy
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus.map_vision import (NODE_BADGE_TEMPLATE, advance_plan, flame_player,
                                  likely_player, node_markers, player_marker,
                                  yellow_flame_player)
from maalimbus.vision import inset_box
from recognition import Journal, LimbusRecognition, MapObservation

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'


def node_badge_template():
    """The crescent emblem every map node hangs under its hexagon, or None."""
    if not hasattr(node_badge_template, 'cache'):
        path = ROOT / 'assets/resource/base' / NODE_BADGE_TEMPLATE
        node_badge_template.cache = cv2.imread(str(path)) if path.exists() else None
    return node_badge_template.cache

PIPELINE_DIR = ROOT / 'build/map-advance-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/map-advance.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


def run_node(tasker, name, deadline):
    job = tasker.post_task(name)
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def observations(directory, name='map_observed'):
    return [json.loads(line) for line in
            (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()
            if json.loads(line).get('event') == name]


def latest_frame(directory):
    for path in sorted(directory.glob('frame-*.png'), reverse=True):
        image = cv2.imread(str(path))
        if image is not None:
            return image, path.name
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--interval', type=float, default=6.0)
    parser.add_argument('--index', type=int, default=0,
                        help='which candidate node to try (bounded search, one per run)')
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/map-advance-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 90 + args.rounds * (args.interval + 25)
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  clicks_sent=0, verified_clear=False, foreground_before=None)
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            return 1
        device['input_policy'] = reason
        controller = build(device, input_enabled=True)
        result.update(device=device, foreground_before=foreground_of(device))
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

        run_node(tasker, 'MapObserve', deadline)
        before = observations(directory)[-1]
        result['before_observation'] = before
        if before['scene'] != 'MAP':
            result.update(refused='page_is_not_an_identified_map', passed=False)
            return 1
        image, frame_name = latest_frame(directory)
        if image is None:
            result.update(refused='no_frame_image_to_read_nodes_from', passed=False)
            return 1
        markers = node_markers(image, template=node_badge_template())
        player = (yellow_flame_player(markers, image) or player_marker(image)
                  or flame_player(markers, image) or likely_player(markers))
        plan = advance_plan(markers, player, args.index)
        result.update(frame=frame_name, markers=[m.node for m in markers], plan=plan,
                      index=args.index)
        if plan['target'] is None:
            result.update(refused=plan['reason'], passed=False)
            return 1
        box = inset_box(tuple(plan['target']), .3)
        x, y, w, h = box
        target = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
        delay = random.randint(350, 750)
        journal.record('map_advance_intent', node=plan['target'], ornament=plan['ornament'],
                       point=list(target), delay_ms=delay, verified_clear=False)
        wait_job(controller.post_click(*target), timeout=10, deadline=deadline)
        result.update(clicks_sent=1, click_point=list(target), delay_ms=delay)
        time.sleep(delay / 1000)
        rounds = []
        for index in range(args.rounds):
            if index:
                time.sleep(args.interval)
            run_node(tasker, 'MapObserve', deadline)
            rounds.append(observations(directory)[-1])
        result['rounds'] = rounds
        result['settled'] = rounds[-1] if rounds else None
        scenes = [r['scene'] for r in rounds]
        result['panel_opened'] = 'NODE_PANEL' in scenes
        result['foreground_after'] = foreground_of(device)
        result['reason'] = ('node_panel_opened' if result['panel_opened']
                            else 'node_click_opened_no_panel')
        result['passed'] = (result['clicks_sent'] == 1 and result['panel_opened']
                            and result['foreground_after'] == result['foreground_before'])
    except Exception as error:
        result.update(reason='map_advance_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}, ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
