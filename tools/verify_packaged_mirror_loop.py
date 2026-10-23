"""Run the installed MirrorTask (MXU Start entry) against the live window.

The packaged app is only proven to automate the dungeon when the task MXU starts
is the task that runs here: `MirrorTask` in the installed pipeline, executed by
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
import hashlib
import re

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


def verdict(record, outcome, started):
    """Entry wiring, bounded progress and dungeon completion are separate facts."""
    steps = (record or {}).get('steps') or []
    reason = (record or {}).get('reason')
    passed = bool(started and outcome.get('task_succeeded') and
                  not outcome.get('timed_out') and not outcome.get('interrupted') and
                  (record or {}).get('passed') and reason == 'window_steps_passed' and
                  steps and all(s.get('passed') or s.get('handled_retry') for s in steps))
    return dict(passed=passed, entry_connected=bool(started),
                bounded_progress_verified=passed,
                dungeon_complete=bool(passed and record.get('verified_clear')),
                stop_reason=reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    # The MuMu device address is a project constant; requiring it to be retyped turned
    # two rounds into argument-parse failures instead of runs.
    parser.add_argument('--address', default='127.0.0.1:16416')
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--input-method', default=None)
    parser.add_argument('--authorize', default='')
    parser.add_argument('--steps', type=int, default=12)
    parser.add_argument('--seconds', type=float, default=240.0)
    parser.add_argument('--gift-plan', default='assets/resource/base/gift-plan.json')
    parser.add_argument('--gift-keyword', default=None,
                        help='Explicit override; otherwise preserve saved launch/team choice')
    parser.add_argument('--shop-refreshes', type=int, default=2)
    parser.add_argument('--observe-only', action='store_true')
    parser.add_argument('--stop-page', help='Stop on first fresh named page before input there')
    parser.add_argument('--entry', choices=('MirrorTask', 'MirrorLoop'), default='MirrorTask')
    parser.add_argument('--gui-log',type=Path,
                        help='Replay the last already-parsed MirrorTask overrides from the local MXU log')
    parser.add_argument('--data-directory', type=Path,
                        help='Explicit private-state binding; defaults to installed app config')
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'build/packaged-mirror-loop-verification.json')
    args = parser.parse_args()
    app = args.app.resolve()
    if not args.observe_only and not runner.authorized(args.authorize):
        granted = runner.granted_nonce()
        print(json.dumps({'passed': False, 'refused': 'live_input_authorized_needs_a_granted_nonce',
                          'hint': f'pass --authorize {granted}' if granted else
                                  f'{runner.AUTHORIZATION} does not grant live input yet',
                          'authorization_file': str(runner.AUTHORIZATION),
                          'granted_nonce': granted}, indent=2))
        return 1
    directory = ROOT / 'evidence/runtime' / ('packaged-mirror-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    result = dict(app=str(app), address=args.address, observe_only=bool(args.observe_only),
                  agent=str(app / 'agent/MaaLimbusAgent.exe'), directory=str(directory),
                  entry=args.entry, steps_requested=args.steps, clicks_sent=0, passed=False)
    import sys as _sys
    from check_freeze import runnable as _runnable, verdict as _verdict
    _freeze = _verdict()
    _gate = _runnable(_freeze, allow_stale=('--allow-stale' in _sys.argv))
    result['freeze'] = _freeze
    result['freeze_gate'] = _gate
    if not _gate['run']:
        result.update(passed=False, refused=_gate['reason'],
                      hint=f"frozen {str(_freeze.get('frozen'))[:8]} head {str(_freeze.get('head'))[:8]};"
                           " refreeze (build/refreeze_agent.py) or pass --allow-stale")
        print(json.dumps(result, ensure_ascii=False)); return 1
    gui_overrides=None
    if args.gui_log:
        if args.entry!='MirrorTask':raise ValueError('GUI choices require the actual MirrorTask entry')
        rows=re.findall(r'entry=MirrorTask, pipelineOverride=(\[.*\])',args.gui_log.read_text(encoding='utf-8'))
        if not rows:raise ValueError('No already-parsed MirrorTask GUI override in this log')
        patches=json.loads(rows[-1]);gui_overrides={}
        if not isinstance(patches,list):raise ValueError('GUI override array required')
        for patch in patches:
            if not isinstance(patch,dict):raise ValueError('Invalid GUI patch')
            for name,value in patch.items():
                if name in gui_overrides:raise ValueError('Overlapping GUI patches require review')
                gui_overrides[name]=value
        result['gui_override_sha256']=hashlib.sha256(rows[-1].encode()).hexdigest()
        result['gui_choice_replayed']=True
        result['gui_click_verified']=False
    else:
        # Without a GUI log the driver used to run the packaged defaults while the GUI
        # held the player's real choices.  Both are read now, so "which team and which
        # build" has one source: the configuration the player actually set.
        from maalimbus import gui_preferences, mirror_task_options
        prefs=gui_preferences.read()
        result['gui_preferences']=gui_preferences.describe(prefs)
        from_gui=mirror_task_options.gui_override(prefs)
        if from_gui:
            gui_overrides=from_gui
            result['gui_choice_replayed']=False
            result['gui_choice_from_config']=sorted(from_gui)
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
        # One custom MainTask contains the full bounded loop. Its reverse calls
        # can pause for a battle animation; a 5s IPC liveness timeout falsely
        # disconnects that running action. The independent task deadline remains.
        agent.set_timeout(int((args.seconds+30)*1000))
        assert agent.bind(resource)
        environment = {**os.environ, 'PI_RESOURCE': json.dumps({'name': 'en'}),
                       'PI_CONTROLLER': json.dumps(device),
                       'MAALIMBUS_EVIDENCE': str(directory),
                       # The loop reads its own run directory from this name; without it
                       # the run lands inside the installed product instead.
                       'MAALIMBUS_RUN_DIR': str(directory)}
        if args.data_directory:
            environment['MAALIMBUS_DATA_PATH'] = str(args.data_directory.resolve())
        result['private_state_binding'] = environment.get('MAALIMBUS_DATA_PATH', str(app/'config'))
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
                if gui_overrides is not None and not resource.override_pipeline(gui_overrides):
                    raise ValueError('Installed resources refused the parsed GUI choices')
                wait_job(controller.post_connection(), timeout=10)
                tasker = Tasker()
                assert tasker.bind(resource=resource, controller=controller)
                parameters = dict(observe_only=bool(args.observe_only), steps=args.steps,
                                  interval=4.0, rounds=3, unknown_rounds=6, map_tries=4,
                                  claim_tries=3, battle_rounds=8, defeat_tries=1,
                                  gift_plan=args.gift_plan,
                                  shop_refreshes=args.shop_refreshes,
                                  run_store='config/user-run-ledger.json', directory='',
                                  budget=args.seconds, stop_page=args.stop_page)
                if args.gift_keyword is not None:
                    parameters['gift_keyword']=args.gift_keyword
                override = {'MirrorLoop': {'timeout': int(args.seconds * 1000),
                                           'custom_action_param': parameters}}
                if args.entry == 'MirrorTask':
                    # MainTask owns the system-wide lease in the Agent process,
                    # just as with MXU. Holding it in this host would reject Start.
                    lease.close()
                    result['lease_owner'] = 'installed MainTask Agent'
                started = time.monotonic()
                outcome = wait_task(tasker, tasker.post_task(args.entry, override),
                                    deadline=started + args.seconds + 30)
                result['task'] = outcome
            finally:
                if tasker is not None and tasker.running:
                    wait_job(tasker.post_stop(), timeout=8)
                try:
                    agent.disconnect()
                except OSError as error:
                    result['disconnect_error']=str(error)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        result['event_names'] = [event['event'] for event in events]
        result['clicks_sent'] = sum(1 for event in events if event['event'] in ('window_intent','unknown_exploration_intent'))
        result['mirror_loop_started'] = any(event['event'] == 'mirror_loop_start' for event in events)
        answer = directory / 'agent-result.json'
        if answer.is_file():
            record = json.loads(answer.read_text(encoding='utf-8'))
            result['agent_result'] = {key: record.get(key) for key in
                                      ('steps', 'clicks_sent', 'verified_clear', 'stopped', 'reason')}
            result['agent_result']['steps'] = len(record.get('steps') or [])
        result.update(verdict(record, result['task'], result['mirror_loop_started']))
        result['scope'] = ('installed task entry + frozen agent + installed resources + real '
                           'controller; bounded progress does not prove dungeon completion or GUI click')
        return 0 if result['passed'] else 1
    finally:
        result['lease'] = str(lease.path)
        lease.close()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
