"""Run the mirror loop in this process, without the packaged agent server (D193).

The packaged agent dies before it can talk to anything: `MaaAgentServer.dll` aborts in
zeromq (`epoll.cpp:73`, then `Socket operation on non-socket [10038]`), which is a build
fault in the framework binary and not in this repository.  Everything the agent does is
also reachable in one process -- `map_live_observe.py` has driven the controller and the
tasker this way since round 1 -- so this tool drives `MirrorRunner` directly: same
journal, same settings, same evidence directory, no agent.

It is a verification tool, not a second agent: it does not accept PI resource params and it
runs one loop with the arguments on its command line.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]

from maa.library import Library
from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus.adb_device import build, discover, foreground_of
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job
from maalimbus import runner

import selfrun_finish

from recognition import (Journal, BattleObservation, BattlePlanObservation, DeploymentProof,
                         DifficultyProof, GlobalSettingsAction, InitialGiftProof,
                         InitialReceiptProof, InputPreflight, LimbusRecognition,
                         LimbusTerminal, MainTaskAction, MapObservation,
                         MirrorLoopAction, StarProof, TeamAction, ThemeObservation)

# The same table `agent/main.py` registers against the agent server, pointed at a client-side
# resource instead.  Kept as data so a new custom is one line here and one line there.
CUSTOM_ACTIONS = ((('limbus_terminal', LimbusTerminal), ('limbus_team', TeamAction),
                   ('limbus_star_proof', StarProof),
                   ('limbus_initial_gift_proof', InitialGiftProof),
                   ('limbus_initial_receipt_proof', InitialReceiptProof),
                   ('limbus_difficulty_proof', DifficultyProof),
                   ('limbus_preflight', InputPreflight),
                   ('limbus_theme_observe', ThemeObservation),
                   ('limbus_deployment_proof', DeploymentProof),
                   ('limbus_battle_plan_observe', BattlePlanObservation),
                   ('limbus_map_observe', MapObservation),
                   ('limbus_battle_observe', BattleObservation),
                   ('limbus_global_settings', GlobalSettingsAction),
                   ('limbus_main_task', MainTaskAction)))


def register(resource, recognition):
    """Register every custom the packaged agent registers, on a plain resource."""
    resource.register_custom_recognition('limbus_scene', recognition)
    for name, factory in CUSTOM_ACTIONS:
        resource.register_custom_action(name, factory(recognition))
    return tuple(name for name, _ in CUSTOM_ACTIONS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--address', required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--seconds', type=float, default=180.0)
    parser.add_argument('--steps', type=int, default=300)
    parser.add_argument('--observe-only', action='store_true')
    parser.add_argument('--locale', default='en')
    args = parser.parse_args()

    directory = ROOT / ('evidence/runtime/packaged-mirror-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    budget = float(args.seconds)
    deadline = time.monotonic() + budget
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController (in process)',
                  observe_only=bool(args.observe_only), budget=budget, steps=[], clicks_sent=0,
                  verified_clear=False, foreground_before=None, input_sent=not args.observe_only)
    journal = Journal(directory)
    loop = None
    try:
        Library.open(args.binary, agent_server=False)
        device_record = discover(args.address, args.adb)
        try:
            result['foreground_before'] = foreground_of(device_record)
        except Exception as error:  # adb may not know this address by that serial
            result['foreground_error'] = str(error)[:160]
        controller = build(device_record, input_enabled=not args.observe_only)
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        recognition = LimbusRecognition(args.locale, journal)
        resource = Resource()
        result['customs'] = register(resource, recognition)
        for layer in ('base', args.locale):
            bundle = ROOT / f'assets/resource/{layer}'
            if bundle.is_dir():
                wait_job(resource.post_bundle(bundle), timeout=30, deadline=deadline)
        tasker = Tasker()
        if not tasker.bind(resource=resource, controller=controller):
            raise RuntimeError('the tasker could not bind the resource and controller')
        inner = runner.MaaDevice(controller, deadline=deadline, tasker=tasker,
                                 target_long_side=runner._TARGET_LONG_SIDE)
        # MaaObserver takes a *context* with tasker/run/journal, not a bare tasker: the
        # agent passes its custom-action context, this tool passes the same three things.
        observer = runner.MaaObserver(SimpleNamespace(tasker=tasker, run=None,
                                                      journal=journal, directory=directory),
                                      directory)
        settings = runner.settings({'steps': args.steps, 'observe_only': bool(args.observe_only),
                                    'address': args.address})
        journal.record('mirror_loop_start', directory=str(directory), budget=budget,
                       deadline=deadline, in_process=True, steps=args.steps,
                       observe_only=bool(args.observe_only), address=args.address)
        snapping = selfrun_finish.Snapshotting(journal, directory, result)
        loop = runner.MirrorRunner(inner, settings=settings, locale=args.locale,
                                   registry=json.loads(runner.REGISTRY.read_text(encoding='utf-8')),
                                   directory=directory, journal=snapping, observer=observer,
                                   result=result)
        loop.configure(deadline=deadline)
        # `round_limit` is how many steps one call may walk (the agent passes the same
        # budget as `steps`), not a cap on unproductive rounds.
        summary = loop.run(steps=args.steps, interval=settings.interval,
                           round_limit=args.steps, deadline=deadline)
        # A tool that replaces the agent also writes the stop row the agent used to write,
        # and the summary goes to disk here because `os._exit` skips `finally` (D195).
        selfrun_finish.summary(snapping, summary, result, directory)
    except BaseException as error:  # the run must leave a cause, whatever it was
        result['error'] = str(error)[:300]
        result['passed'] = False
        # The error path writes the same stop row and summary the success path does, so a
        # tool run is readable through `run_metrics.ending` whichever way it ended (D195).
        selfrun_finish.summary(journal, {'passed': False, 'reason': type(error).__name__},
                               result, directory)
        result['error'] = str(error)[:300]
        result['passed'] = False
    finally:
        try:
            lease.close()
        except Exception:
            pass
        # The summary is written whatever happened above: a run that reached a floor and
        # then tripped over its own bookkeeping still has to leave the numbers (D195).
        try:
            path = directory / 'events.jsonl'
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                    if line.strip()] if path.exists() else []
            selfrun_finish.tally(rows, result)
        except Exception as error:
            result['summary_error'] = str(error)[:200]
        try:
            selfrun_finish.Snapshotting(journal, directory, result).snapshot()
        except Exception as error:
            result['summary_error'] = str(error)[:200]
        print(json.dumps({key: result.get(key) for key in
                          ('passed', 'events', 'stop', 'floors', 'error')}))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
