"""One bounded window: walk the live dungeon loop and record every page it meets.

This is the verification-window engine. A window is one continuous live session
that advances the run through the pages the script must recognise, records each
page (frame + full OCR + scene + the controls read from that page), and stops the
moment it meets a page it cannot prove.

Rules:
  * exactly one input per step, chosen by ``maalimbus.window.plan_step``;
  * the point is sampled inside an inset of the planned box with a bounded delay;
  * the successor page must be one of the expected pages, otherwise the step is
    recorded as ``unexpected_successor`` and the window stops;
  * a page with no proven control is recorded and the window stops (never guessed);
  * ``--observe-only`` sends no input at all.

The gate is the same as the other live tools: ``build/map-probe-authorization.json``
must grant ``live_input_authorized`` for the nonce passed on the command line.
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
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus import anchors
from maalimbus.adb_device import build, discover, foreground_of, input_policy
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus.map_vision import (advance_candidates, flame_player, likely_player,
                                  node_markers, player_marker)
from maalimbus.vision import inset_box
from maalimbus.window import NODE, plan_step, resolve_overlay, step_result
from recognition import (BattleObservation, Journal, LimbusRecognition,
                         MapObservation)

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'
REGISTRY = ROOT / 'assets/resource/base/anchors.json'
PIPELINE_DIR = ROOT / 'build/window-debug'
PIPELINE = {
    'WindowMapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
    'WindowBattleObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_battle_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
    # Mirror menu card: the recognition owns the click box, so the window never
    # invents a coordinate for the dungeon entry.
    'WindowDrive': {
        'recognition': 'Custom', 'custom_recognition': 'limbus_scene',
        'custom_recognition_param': {'scene': 'DRIVE', 'token': 'mirror_menu',
                                    'roi': [.23, .25, .46, .55]},
        'action': 'Click', 'target': True, 'post_delay': 1000, 'max_hit': 1,
        'next': [], 'on_error': [],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/window.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


def controls_by_id(registry: dict) -> dict:
    """Anchor name -> proven pixel box, from the anchors registry."""
    controls = {}
    for page in registry.get('pages', []):
        for control in page.get('controls', []):
            box = (control.get('verified_on') or {}).get('box')
            if box is not None:
                controls[control['id']] = list(box)
    return controls


def run_node(tasker, name, deadline):
    job = tasker.post_task(name)
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def events(directory, name):
    return [json.loads(line) for line in
            (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()
            if json.loads(line).get('event') == name]


def latest_frame(directory):
    for path in sorted(directory.glob('frame-*.png'), reverse=True):
        image = cv2.imread(str(path))
        if image is not None:
            return image, path.name
    return None, None


def observe(tasker, directory, deadline):
    """Read the live page once and return its journal record."""
    run_node(tasker, 'WindowMapObserve', deadline)
    record = events(directory, 'map_observed')[-1]
    if record['scene'] in ('BATTLE_HUD', 'BATTLE_PLANNING'):
        run_node(tasker, 'WindowBattleObserve', deadline)
        record = events(directory, 'battle_observed')[-1]
    return record


def candidates_of(directory, record):
    """Node boxes for a MAP page, read from the frame the observation used."""
    if record['scene'] != 'MAP':
        return None, None
    image, name = latest_frame(directory)
    if image is None:
        return None, None
    markers = node_markers(image)
    player = (player_marker(image) or flame_player(markers, image)
              or likely_player(markers))
    return name, [list(marker.node) for marker in advance_candidates(markers, player)]


def overlay_hit(registry, directory, record):
    """True when the tutorial overlay's own continue control is on screen.

    The overlay's wording changes from card to card, so its identity is the
    control itself: a visible continue glyph means whatever is behind it is still
    covered and must not be treated as actionable.
    """
    image, name = latest_frame(directory)
    if image is None:
        return None
    height, width = image.shape[:2]
    observation = {'size': [width, height],
                   'image_sha256': record.get('image_sha256')}
    report = anchors.evaluate(registry, observation, page='tutorial',
                              image_path=str(directory / name),
                              template_root=ROOT / 'assets/resource/base')
    for page in report['pages']:
        for anchor in list(page.get('identity') or []) + list(page.get('controls') or []):
            if anchor.get('id') == 'tutorial.next_glyph':
                return anchor.get('hit')
    return None


def resolve_scene(registry, directory, record):
    """Page identity, with the tutorial overlay taking precedence while it is up."""
    return resolve_overlay(record['scene'],
                           overlay_hit=bool(overlay_hit(registry, directory, record)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--steps', type=int, default=1,
                        help='how many planned inputs this window may send')
    parser.add_argument('--rounds', type=int, default=3,
                        help='read-only observations used to settle each step')
    parser.add_argument('--interval', type=float, default=4.0)
    parser.add_argument('--observe-only', action='store_true',
                        help='record the page and send no input at all')
    parser.add_argument('--report', type=Path, default=None)
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/window-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120 + args.steps * (args.rounds * (args.interval + 25))
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    controls = controls_by_id(registry)
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  observe_only=bool(args.observe_only), steps=[], clicks_sent=0,
                  verified_clear=False, foreground_before=None)
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            return 1
        device['input_policy'] = reason
        controller = build(device, input_enabled=not args.observe_only)
        result.update(device=device, foreground_before=foreground_of(device))
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        journal = Journal(directory)
        recognition = LimbusRecognition('en', journal)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', recognition)
        resource.register_custom_action('limbus_map_observe', MapObservation(recognition))
        resource.register_custom_action('limbus_battle_observe', BattleObservation(recognition))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'),
                     timeout=20, deadline=deadline)
        wait_job(resource.post_bundle(PIPELINE_DIR), timeout=20, deadline=deadline)
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)

        page = None
        tutorial_cards = set()
        for step in range(max(0, args.steps)):
            record = observe(tasker, directory, deadline)
            page = resolve_scene(registry, directory, record)
            frame, candidates = candidates_of(directory, record)
            sha = record.get('image_sha256')
            if page == 'TUTORIAL' and sha in tutorial_cards:
                result['steps'].append({
                    'step': step, 'page_before': page, 'scene_before': record['scene'],
                    'frame': frame, 'observation': record, 'plan': None,
                    'candidates': candidates, 'passed': False, 'clicks_sent': 0,
                    'reason': 'tutorial_card_repeated',
                    'stopped': 'tutorial_card_repeated'})
                break
            if page == 'TUTORIAL' and sha:
                tutorial_cards.add(sha)
            plan = plan_step(page, controls=controls,
                             start_box=record.get('start_box'),
                             auto_assign=record.get('auto_assign_buttons'),
                             candidates=candidates)
            entry = {'step': step, 'page_before': page, 'scene_before': record['scene'],
                     'frame': frame, 'observation': record, 'plan': plan,
                     'candidates': candidates}
            if plan['action'] not in ('click', NODE) or args.observe_only:
                entry.update(step_result(plan, sent=False, before=page, after=None,
                                         page=page))
                entry['stopped'] = ('observe_only' if args.observe_only
                                    else plan['reason'])
                result['steps'].append(entry)
                break
            point = None
            delay = random.randint(350, 750)
            if plan['action'] == NODE:
                journal.record('window_intent', page=page, node=plan['node'],
                               reason=plan['reason'], delay_ms=delay)
                run_node(tasker, plan['node'], deadline)
            else:
                box = inset_box(tuple(plan['target']), .3)
                x, y, w, h = box
                point = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
                journal.record('window_intent', page=page, target=list(plan['target']),
                               reason=plan['reason'], point=list(point), delay_ms=delay)
                wait_job(controller.post_click(*point), timeout=10, deadline=deadline)
            result['clicks_sent'] += 1
            entry.update(click_point=None if point is None else list(point), delay_ms=delay)
            time.sleep(delay / 1000)
            settled = None
            settled_page = None
            before_sha = record.get('image_sha256')
            for index in range(max(1, args.rounds)):
                if index:
                    time.sleep(args.interval)
                settled = observe(tasker, directory, deadline)
                settled_page = resolve_scene(registry, directory, settled)
                if settled_page not in (page, 'UNKNOWN'):
                    break
                # A tutorial card keeps the same page label but changes the pixels,
                # so a changed frame is the only evidence that the click landed.
                if settled.get('image_sha256') not in (None, before_sha):
                    break
            entry.update(page_after=settled_page, settled=settled,
                         scene_after=settled['scene'])
            entry.update(step_result(plan, sent=True, before=page,
                                     after=settled_page, page=settled_page))
            result['steps'].append(entry)
            if not entry['passed']:
                entry['stopped'] = entry['reason']
                break
        result['foreground_after'] = foreground_of(device)
        last = result['steps'][-1] if result['steps'] else None
        result['page_before'] = None if last is None else last['page_before']
        result['page_after'] = None if last is None else last.get('page_after')
        result['passed'] = bool(result['steps']) and all(s['passed'] for s in result['steps'])
        result['reason'] = ('window_steps_passed' if result['passed']
                            else (last or {}).get('stopped', 'no_step_recorded'))
    except Exception as error:
        result.update(reason='window_failed', error=str(error), passed=False)
        raise
    finally:
        report = directory / 'result.json'
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8')
        if args.report:
            Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ('steps', 'device', 'foreground_before',
                                       'foreground_after')},
                         ensure_ascii=False, indent=1))
        for entry in result['steps']:
            print(json.dumps({'step': entry['step'], 'page_before': entry['page_before'],
                              'page_after': entry.get('page_after'),
                              'action': entry['action'], 'reason': entry['reason'],
                              'passed': entry['passed'],
                              'stopped': entry.get('stopped')}, ensure_ascii=False))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
