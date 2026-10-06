"""One bounded Android touch step in a battle, chosen from the page itself.

The step is exactly one of:
  * `start_turn` — the assigned battle shows `START`, so submit the turn;
  * `auto_assign` — the battle shows `Win Rate`/`Damage`, so ask the game to assign
    the turn by win rate (the touch equivalent of the upstream win-rate step).

It refuses without the nonce in `build/map-probe-authorization.json`, refuses when
the fresh read-only observation is not the combat HUD, performs at most one Maa
`Click` through the matching pipeline node, then settles the page with bounded
read-only observations. It never picks a skill or an enemy target and never sends a
key; victory and floor clears are never inferred here.
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
from recognition import Journal, LimbusRecognition, BattleObservation

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'


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


def events_of(directory, name):
    return [json.loads(line) for line in
            (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()
            if json.loads(line).get('event') == name]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None,
                        help='optional adb path restricting discovery; omit to let '
                             'MaaToolkit search and supply the emulator config')
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--interval', type=float, default=5.0)
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/battle-step-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 150 + args.rounds * (args.interval + 25)
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  clicks_sent=0, turn_submitted=False, victory_verified=False,
                  verified_clear=False,
                  foreground_before=None)
    try:
        Library.open(args.binary, agent_server=False)
        device = discover(args.address, args.adb)
        result['foreground_before'] = foreground_of(device)
        Toolkit.init_option(ROOT / 'build/battle-step-debug')
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
        resource.register_custom_action('limbus_battle_observe', BattleObservation(recognition))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'), timeout=20, deadline=deadline)
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)

        result['before'] = run_node(tasker, 'BattleObserve', deadline)
        before = events_of(directory, 'battle_observed')
        result['before_observation'] = before[-1] if before else None
        page = before[-1] if before else None
        if page is None or page['scene'] != 'BATTLE_HUD':
            result.update(refused='page_is_not_the_combat_hud', passed=False)
            return 1
        if page.get('start_box'):
            result['action'] = 'start_turn'
            node = 'BattleStartTurn'
        elif page.get('auto_assign_buttons'):
            result['action'] = 'auto_assign'
            node = 'BattleAutoAssign'
        else:
            result.update(refused='battle_page_has_no_known_action', passed=False)
            return 1

        result['step'] = run_node(tasker, node, deadline)
        intents = events_of(directory, 'battle_turn_intent')
        if result['action'] == 'start_turn':
            result['intent'] = intents[-1] if intents else None
            result['clicks_sent'] = len(intents)
            result['turn_submitted'] = bool(intents)
            if not intents:
                result.setdefault('blocked', events_of(directory, 'battle_turn_blocked')[-1:])
        else:
            assigns = events_of(directory, 'battle_auto_assign_intent')
            result['intent'] = assigns[-1] if assigns else None
            result['clicks_sent'] = len(assigns)
            if not assigns:
                result.setdefault('blocked', events_of(directory, 'battle_auto_assign_blocked')[-1:])

        rounds = []
        for index in range(args.rounds):
            if index:
                time.sleep(args.interval)
                run_node(tasker, 'BattleObserve', deadline)
            rounds.append(events_of(directory, 'battle_observed')[-1])
        result['rounds'] = rounds
        result['settled'] = rounds[-1] if rounds else None
        # A no-op step must be visible, never repeated blindly: an auto_assign that
        # left the same turn without producing START did not take effect.
        if (result.get('action') == 'auto_assign' and rounds
                and result['settled'].get('start_box') is None
                and result['settled'].get('turn') == page.get('turn')):
            result['auto_assign_had_no_effect'] = True
        result['foreground_after'] = foreground_of(device)
        result['reason'] = 'bounded_battle_step_recorded'
        result['passed'] = (result['clicks_sent'] <= 1
                            and not result.get('auto_assign_had_no_effect')
                            and result['foreground_after'] == result['foreground_before'])
    except Exception as error:
        result.update(reason='battle_step_failed', error=str(error), passed=False)
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}, ensure_ascii=False, indent=1))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
