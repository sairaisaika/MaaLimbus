"""Press the pre-battle team page's `Battle!` action once, then record the result.

Same live-input gate as the other probes: it refuses without the nonce in
`build/map-probe-authorization.json`, only clicks when a *fresh* recognition of the
current page yields the team page's `Battle!` box, samples inside an inset box with
a bounded delay, clicks exactly once, never sends a key, and then settles the
successor page with bounded read-only observations.
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
PIPELINE_DIR = ROOT / 'build/team-page-debug'
PIPELINE = {
    'MapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/team-page.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


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
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--interval', type=float, default=6.0)
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/team-page-battle-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120 + args.rounds * (args.interval + 25)
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  clicks_sent=0, verified_clear=False,
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

        result['before'] = observe(tasker, deadline)
        before = observations(directory)[-1]
        result['before_observation'] = before
        if before['scene'] != 'PRE_BATTLE_TEAM' or not before.get('battle_box'):
            result.update(refused='page_is_not_the_pre_battle_team_page', passed=False)
            return 1
        box = tuple(before['battle_box'])
        x, y, w, h = inset_box(box, .25)
        target = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
        delay = random.randint(350, 750)
        journal.record('team_page_battle_intent', battle_box=list(box), target=list(target),
                       participants=before.get('participant_texts'), delay_ms=delay,
                       verified_clear=False)
        wait_job(controller.post_click(*target), timeout=10, deadline=deadline)
        result.update(clicks_sent=1, click_target=list(target), battle_box=list(box), delay_ms=delay,
                      participants=before.get('participant_texts'))
        time.sleep(delay / 1000)
        rounds = []
        for index in range(args.rounds):
            task = observe(tasker, deadline)
            observed = observations(directory)[-1]
            rounds.append(dict(round=index + 1, task=task, observation=observed))
            if observed['scene'] not in ('UNKNOWN',):
                break
            if index + 1 < args.rounds:
                time.sleep(args.interval)
        result['rounds'] = rounds
        result['settled'] = rounds[-1]['observation'] if rounds else None
        result['foreground_after'] = foreground(args.adb, args.address)
        result['reason'] = 'team_page_battle_successor_recorded'
        result['passed'] = (result['clicks_sent'] == 1
                            and result['foreground_after'] == result['foreground_before'])
    except Exception as error:
        result.update(reason='team_page_battle_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}, ensure_ascii=False, indent=1))
        print(json.dumps([r['observation'] for r in result.get('rounds', [])], ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
