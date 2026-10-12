"""Run the packaged product's own MirrorLoop entry against the live window.

The packaged app is only proven to automate the dungeon when the task MXU starts
is the task that runs here: `MirrorLoop` in the installed pipeline, executed by
the frozen `MaaLimbusAgent.exe`, driving a real device controller. This tool
starts exactly that -- the same entry, the same agent binary, the same resources
-- with a bounded step budget, and records what the frozen loop did.

The gate is the project's live-input gate: without `--observe-only`, the nonce
must be granted by ``build/map-probe-authorization.json``.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]

from maa.agent_client import AgentClient
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus.adb_device import build, discover, foreground_of, input_policy, pin_input
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus import runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--address', required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--input-method', default=None)
    parser.add_argument('--authorize', default='')
    parser.add_argument('--steps', type=int, default=12)
    parser.add_argument('--seconds', type=float, default=240.0)
    parser.add_argument('--observe-only', action='store_true')
    args = parser.parse_args()
    app = args.app.resolve()
    if not args.observe_only and not runner.authorized(args.authorize):
        print(json.dumps({'passed': False, 'refused': 'live_input_authorized_needs_a_granted_nonce',
                          'hint': f'{runner.AUTHORIZATION} must grant {args.authorize}'}, indent=2))
        return 1
    directory = ROOT / 'evidence/runtime' / ('packaged-mirror-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    result = dict(app=str(app), address=args.address, observe_only=bool(args.observe_only),
                  agent=str(app / 'agent/MaaLimbusAgent.exe'), directory=str(directory),
                  steps_requested=args.steps, clicks_sent=0, passed=False)
    Library.open(app / 'maafw', agent_server=False)
    Toolkit.init_option(directory / 'debug')
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    record = None
    agent = None
    child = None
    tasker = None
    try:
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result['refused'] = reason
            return 1
        device['input_policy'] = reason
        if args.input_method:
            device = pin_input(device, args.input_method)
            device['input_policy'] = reason + '+pinned_' + args.input_method
        controller = build(device, input_enabled=not args.observe_only)
        result['device'] = device
        result['foreground_before'] = foreground_of(device)
        wait_job(controller.post_connection(), timeout=15)
        controller.set_screenshot_target_long_side(1920)
        resource, agent = Resource(), AgentClient()
        agent.set_timeout(5000)
        assert agent.bind(resource)
        environment = {**os.environ, 'PI_RESOURCE': json.dumps({'name': 'en'}),
                       'PI_CONTROLLER': json.dumps(device),
                       'MAALIMBUS_EVIDENCE': str(directory),
                       # The loop reads its own run directory from this name; without it
                       # the run lands inside the installed product instead.
                       'MAALIMBUS_RUN_DIR': str(directory)}
        with (directory / 'agent.stdout.log').open('w') as stdout, \
                (directory / 'agent.stderr.log').open('w') as stderr:
            child = subprocess.Popen([result['agent'], agent.identifier], cwd=str(app),
                                     env=environment, stdout=stdout, stderr=stderr,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                if not agent.connect():
                    raise RuntimeError('Packaged Agent IPC connection failed')
                result['custom_actions'] = sorted(agent.custom_action_list)
                assert 'limbus_mirror_loop' in agent.custom_action_list, \
                    'The packaged agent does not register the whole-dungeon loop'
                for layer in ('base', 'en'):
                    wait_job(resource.post_bundle(app / f'assets/resource/{layer}'), timeout=30)
                wait_job(controller.post_connection(), timeout=10)
                tasker = Tasker()
                assert tasker.bind(resource=resource, controller=controller)
                parameters = dict(observe_only=bool(args.observe_only), steps=args.steps,
                                  interval=4.0, rounds=3, unknown_rounds=6, map_tries=4,
                                  claim_tries=3, battle_rounds=8, defeat_tries=1,
                                  gift_plan='assets/resource/base/gift-plan.json',
                                  run_store='config/user-run-ledger.json', team=5, directory='')
                override = {'MirrorLoop': {'timeout': int(args.seconds * 1000),
                                           'custom_action_param': parameters}}
                started = time.monotonic()
                outcome = wait_task(tasker, tasker.post_task('MirrorLoop', override),
                                    deadline=started + args.seconds + 30)
                result['task'] = outcome
            finally:
                if tasker is not None and tasker.running:
                    wait_job(tasker.post_stop(), timeout=8)
                agent.disconnect()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        result['event_names'] = [event['event'] for event in events]
        result['clicks_sent'] = sum(1 for event in events if event['event'] == 'window_intent')
        result['mirror_loop_started'] = any(event['event'] == 'mirror_loop_start' for event in events)
        answer = directory / 'agent-result.json'
        if answer.is_file():
            record = json.loads(answer.read_text(encoding='utf-8'))
            result['agent_result'] = {key: record.get(key) for key in
                                      ('steps', 'clicks_sent', 'verified_clear', 'stopped', 'reason')}
            result['agent_result']['steps'] = len(record.get('steps') or [])
        result['passed'] = bool(result['mirror_loop_started'] and agent is not None)
        result['scope'] = ('packaged MirrorLoop entry + frozen agent + installed resources + real '
                           'device controller; the loop ran inside the product for a bounded budget')
        return 0 if result['passed'] else 1
    finally:
        result['lease'] = str(lease.path)
        (ROOT / 'build/packaged-mirror-loop-verification.json').write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
