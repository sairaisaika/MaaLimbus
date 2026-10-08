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

The loop itself is not here: it lives in :mod:`maalimbus.runner`, so that this CLI
and a Maa agent custom action drive one implementation of it. This file keeps only
what is local to the command line -- the flags, the device it builds, the evidence
directory, the ledger, and the printing.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus.adb_device import (build, discover, foreground_any_of, foreground_of,
                                  input_policy, pin_input)
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job
from maalimbus import session_flow as flows
from maalimbus.storage import RunStore, read_json
from maalimbus import runner as loop
from maalimbus.runner import (AUTHORIZATION, PIPELINE_DIR, MirrorRunner, LocalDevice,
                              authorized, observed_page, one_shot_click,
                              one_shot_swipe, prepare)
from recognition import (BattleObservation, Journal, LimbusRecognition,
                         MapObservation)

REGISTRY = loop.REGISTRY

#: ``tools/map_zoom.py`` imports the gate from this module, so the names stay here.
__all__ = ['AUTHORIZATION', 'REGISTRY', 'ROOT', 'authorized', 'build_parser', 'main',
           'prepare']


def build_parser():
    """The window's own flags, exactly as this command has always published them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--input-method', default=None,
                        help='pin the ADB input method discovery offered (AdbShell, '
                             'MinitouchAndAdbKey, Maatouch, EmulatorExtras). Discovery '
                             'picks the highest-priority one Maa offers, and on this '
                             'MuMu both Maatouch and MinitouchAndAdbKey stopped '
                             'reaching the app while plain adb shell input tap kept '
                             'working, so the method may be pinned for a run')
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--steps', type=int, default=1,
                        help='how many planned inputs this window may send')
    parser.add_argument('--rounds', type=int, default=3,
                        help='read-only observations used to settle each step')
    parser.add_argument('--unknown-rounds', type=int, default=30,
                        help='how many consecutive UNKNOWN observations to wait through '
                             'before calling the page unreadable (loading screens, the turn '
                             'animation and the victory banner all read as UNKNOWN and are '
                             'not refusals; the victory banner alone held the screen for '
                             'about 25 s in window-20261006-033014, and the post-battle story '
                             'that follows it plays for minutes as a sequence of dialogue '
                             'frames -- live window-20261007-174525/frame-0191..0196 are six '
                             'of them, each with its own hash -- which is what ran the old '
                             'budget of 12 out at step 60 of run-continue-14)')
    parser.add_argument('--battle-rounds', type=int, default=8,
                        help='how many consecutive battle observations may report the same '
                             'wave and turn before the fight is called stalled; assigning and '
                             'submitting legitimately repeat for many turns, so the bound is '
                             'on the readouts moving, not on the clicks repeating')
    parser.add_argument('--interval', type=float, default=4.0)
    parser.add_argument('--map-tries', type=int, default=8,
                        help='how many map nodes one MAP step may try: a node that is not '
                             'connected to where the run stands opens no panel and is a '
                             'no-op, so the next candidate is tried instead of stopping '
                             '(a floor-1 frame shows up to six nodes, and only the ones '
                             'joined to the player by a path can open a panel)')
    parser.add_argument('--page-tries', type=int, default=3,
                        help='how many times a page whose reading is missing (a transition, '
                             'or a dialog still fading in) is looked at again before the run '
                             'stops')
    parser.add_argument('--map-points', default='',
                        help='calibration override for the map: semicolon-separated x,y points '
                             'in 1280-space the run may click instead of its own candidates '
                             '(the player asked for the map to be zoomed out and calibrated, '
                             'm10541); empty means the frame is read as usual')
    parser.add_argument('--team', type=int, default=5,
                        help='which TEAMS slot the rotation brings on the loadout page '
                             '(1..7): the official ledger stands at team 5, so the '
                             'planner clicks that slot once and then Confirm')
    parser.add_argument('--run-store', type=Path, default=None,
                        help='rotation ledger to walk with (config/user-run-ledger.json): '
                             'it names the team this run brings and records the five floor '
                             'clears, the final victory, the claimed reward and the entry '
                             'back in, each one proved by the frame it was read from. '
                             'Without it the window uses --team and records nothing')
    parser.add_argument('--graces', default='1,3,5,6,8',
                        help='Grace cards the run buys, as 1-based board positions in '
                             'the order to try; unaffordable ones are skipped (the '
                             'player asked for 1,3,5,6,8 while testing)')
    parser.add_argument('--grace-budget', type=int, default=60,
                        help='starlight the Graces page may spend when its own '
                             '"Available" counter does not read; the live page showed '
                             'Owned 7541 -> Available 60')
    parser.add_argument('--gift-keyword', default='bleed',
                        help='keyword column the starting E.G.O Gift comes from; the '
                             'rotation currently runs the Bleed team, so its column '
                             'names the first gift to take')
    parser.add_argument('--gift-plan', default='assets/resource/base/gift-plan.json',
                        help='file naming the starting gift per team attribute: a '
                             'fixed gift is a plan whose every attribute holds the '
                             'same name')
    parser.add_argument('--gift-search', choices=('refuse', 'select'), default='refuse',
                        help='what to do on the optional E.G.O Gift Search page: the '
                             'player asked for it to be refused, which spends no '
                             'starlight; "select" instead leaves through Select')
    parser.add_argument('--loop-guard', type=int, default=3,
                        help='stop after the same page/action/target plan passed this many '
                             'times in one visit to one page: a misleading overlay once '
                             'produced twelve passed rounds of TUTORIAL then To Battle! with '
                             'nothing changing. Leaving the page resets the counts, so the '
                             'three separate cutscenes a floor-3 run skipped are not a loop. '
                             'The guide book itself is exempt, because it legitimately '
                             'advances card by card from the same control')
    parser.add_argument('--claim-tries', type=int, default=6,
                        help='stop after this many consecutive steps inside the claim family '
                             '(RUN_CLAIM, RUN_REWARD_DIALOG, RUN_REWARD_CONFIRM): claiming a '
                             'run hops between those three pages, so the per-page loop guard '
                             'resets on every hop and cannot see the loop. Live run103 '
                             'alternated two claim buttons for twenty steps before this '
                             'counter existed, and repeating a claim is forbidden outright')
    parser.add_argument('--observe-page', action='store_true',
                        help='read the live page once and print its scene and OCR tokens '
                             'as JSON, then stop: the cheap way to see a screen without '
                             'storing and reading a screenshot, and it sends no input')
    parser.add_argument('--observe-only', action='store_true',
                        help='record the page and send no input at all')
    parser.add_argument('--defeat-tries', type=int, default=2,
                        help='how many times a wiped stage may be retried in one window '
                             '(default 2): the retry is the only input on that dialog that '
                             'keeps the run alive, and once the tries are spent nothing is '
                             'sent, so the decision to accept the deaths stays with the '
                             'player')
    parser.add_argument('--defeat-accept', action='store_true',
                        help='after the retries are spent, press the dialog\'s own "Accept '
                             'results and return to Stage select" row instead of stopping: '
                             'the run is then filed as abandoned by the ledger (rotation '
                             'unchanged) and the next entry starts a fresh one. Off by '
                             'default, because accepting the deaths ends the run')
    parser.add_argument('--stop-page', default=None,
                        help='stop the window the moment this page is observed: a long '
                             'session (a run that ends with the settlement and then goes '
                             'straight back in) can be handed back before the next input '
                             'starts something the caller did not ask for')
    parser.add_argument('--click-box', action='append', default=None,
                        help='x,y,w,h: send exactly one click and record the before/'
                             'after frames, for a control the anchors do not cover yet. '
                             'Repeat the option to send several clicks in one run')
    parser.add_argument('--reward-action', choices=('claim','confirm','receipt','pass'), default=None,
                        help='One scoped durable paid reward control, with fresh native proof')
    parser.add_argument('--swipe', action='append', default=None,
                        help='x1,y1,x2,y2[,duration_ms]: send exactly one swipe in '
                             'frame coordinates and record the before/after frames, '
                             'for a gesture the anchors do not cover yet (the map '
                             'scroll and the team page both need one)')
    parser.add_argument('--flow', default=None,
                        help='run one or more named session flows, comma-separated and in '
                             'order (see maalimbus.session_flow): the walk from a cold '
                             'client to the Mirror Dungeon card is data, so repeating it is '
                             'one command instead of a chain of hand-aimed one-shot clicks. '
                             'The window stops when the flows are done unless --after-flow '
                             'is given, which keeps driving the page loop for --steps')
    parser.add_argument('--after-flow', action='store_true',
                        help='after the flow chain, keep driving the page loop (--steps) '
                             'instead of stopping at the last flow step')
    parser.add_argument('--flow-list', action='store_true',
                        help='print the named flows and exit, without touching a device')
    parser.add_argument('--label', default='one_shot_click',
                        help='what --click-box is aiming at, for the evidence record')
    parser.add_argument('--report', type=Path, default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    flow_names = [name.strip() for name in (args.flow or '').split(',') if name.strip()]
    unknown_flows = [name for name in flow_names if name not in flows.names()]
    if unknown_flows:
        raise SystemExit('unknown flow(s): %s; known: %s'
                         % (', '.join(unknown_flows), ', '.join(flows.names())))
    if args.flow_list:
        for name in flows.names():
            for step in flows.flow(name):
                print(json.dumps({'flow': name, 'step': step.id, 'kind': step.kind,
                                  'pattern': step.pattern,
                                  'roi': None if step.roi is None else list(step.roi),
                                  'repeat': step.repeat, 'optional': bool(step.optional),
                                  'timeout_s': step.timeout_s, 'note': step.note},
                                 ensure_ascii=False))
        return 0
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/window-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    run_store = None
    run_id = None
    if args.run_store is not None and not args.observe_only:
        # The rotation ledger owns the team this run brings. It is opened before the
        # window starts so the loadout page is planned with the ledger's slot, not the
        # --team default; an existing active run is continued rather than restarted.
        teams = [SimpleNamespace(slot=slot) for slot in
                 (read_json(ROOT / args.run_store)['team_slots']
                  if (ROOT / args.run_store).exists() else [args.team])]
        run_store = RunStore(ROOT / args.run_store, teams)
        run_id = run_store.start()
        args.team = run_store.team_slot
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120 + args.steps * (args.rounds * (args.interval + 25)) \
        + (args.unknown_rounds + 1) * (args.interval + 20)
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  observe_only=bool(args.observe_only), steps=[], clicks_sent=0,
                  verified_clear=False, foreground_before=None)
    if run_store is not None:
        result['run_ledger'] = dict(path=str(args.run_store), run=run_id,
                                    team=run_store.team_slot,
                                    rotation=run_store.data['rotation'])
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            return 1
        device['input_policy'] = reason
        if args.input_method:
            device = pin_input(device, args.input_method)
            device['input_policy'] = reason + '+pinned_' + args.input_method
        controller = build(device, input_enabled=not args.observe_only)
        # A flow that opens with start_app owns the launch, so the client is allowed to be
        # down: the window that is actually in front is recorded first, and Maa's own
        # start-app call (never a desktop launcher) is what brings Limbus up. Every other
        # session still refuses to touch a window it has not identified.
        cold_start = bool(flow_names) and flows.flow(flow_names[0])[0].kind == 'start_app'
        if cold_start:
            result.update(device=device, launched_by_flow=True,
                          foreground_before=foreground_any_of(device))
        else:
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

        # The controller is built; from here the loop is the library's. The window is
        # handed the device it must drive and the directory it must record into, and
        # this file keeps only the flags, the setup above, and the printing below.
        window = MirrorRunner(
            LocalDevice(controller, device=device, tasker=tasker, deadline=deadline),
            settings=args, registry=registry, store=run_store, directory=directory,
            journal=journal, flow=flow_names, run_id=run_id, result=result)
        window.configure(deadline=deadline)

        if args.observe_page:
            result['observed'] = observed_page(window.observer, registry, args,
                                               journal=journal, deadline=deadline)
            result['passed'] = True
            result['reason'] = 'page_observed'
            return 0
        if args.reward_action:
            if args.observe_only or run_store is None or args.click_box or args.swipe or flow_names:
                raise ValueError('Reward action cannot be combined with other input modes')
            from maalimbus.paid_reward_action import prepare as prepare_reward
            def preflight(record):
                # The observer persists the full native cost proof in the latest frame JSON.
                frame=loop.frame_file(directory)
                current=json.loads(frame.read_text(encoding='utf-8'))
                return prepare_reward(args.reward_action,current,run_store.path.parent,run_id,str(frame))
            entry=one_shot_click(window.device,window.observer,[0,0,1,1],
                label='paid_reward_'+args.reward_action,deadline=deadline,journal=journal,
                rounds=args.rounds,interval=args.interval,preflight=preflight)
            entry['step']=0
            window.artifacts['steps'].append(entry)
            window.artifacts['clicks_sent']+=1
            result=window.summary()
            return 0 if entry['passed'] else 1
        if flow_names:
            for name in flow_names:
                problems = flows.validate(name)
                if problems:
                    raise SystemExit('; '.join(problems))
            result['flow'] = ','.join(flow_names)
            window.artifacts['flow'] = result['flow']
            result['flow_steps'] = window.artifacts['flow_steps']
            for name in flow_names:
                # The chain is walked in the order given, and each flow's steps land in
                # one flat record: a cold start is launch -> to_mirror -> enter_mirror,
                # and a window that stopped between them would leave the client idle.
                result['flow_steps'].extend(window._flow(deadline, flows.flow(name),
                                                         bool(args.observe_only)))
                if any(not (entry.get('passed') or entry.get('reason') == 'observe_only')
                       for entry in result['flow_steps']):
                    result = window.summary()
                    return 1
        boxes = []
        for spec in (args.click_box or []):
            parts = [int(value) for value in spec.replace(' ', '').split(',')]
            if len(parts) != 4:
                raise ValueError('--click-box needs x,y,w,h')
            boxes.append(parts)
        for index, parts in enumerate(boxes):
            entry = one_shot_click(window.device, window.observer, parts,
                                   label=args.label,
                                   index=None if len(boxes) == 1 else index,
                                   deadline=deadline, journal=journal,
                                   rounds=args.rounds, interval=args.interval)
            window.artifacts['steps'].append({'step': index, **entry})
            window.artifacts['clicks_sent'] += 1
        swipes = []
        for spec in (args.swipe or []):
            parts = [int(value) for value in spec.replace(' ', '').split(',')]
            if len(parts) not in (4, 5):
                raise ValueError('--swipe needs x1,y1,x2,y2[,duration_ms]')
            swipes.append(parts)
        for index, parts in enumerate(swipes):
            entry = one_shot_swipe(window.device, window.observer, parts,
                                   label=args.label,
                                   index=None if len(swipes) == 1 else index,
                                   deadline=deadline, journal=journal,
                                   rounds=args.rounds, interval=args.interval)
            window.artifacts['steps'].append({'step': index, **entry})
            window.artifacts['swipes_sent'] = result.get('swipes_sent', 0) + 1
        goal = 0 if (boxes or swipes) else (
            max(0, args.steps) if (not flow_names or args.after_flow) else 0)
        if goal:
            # The library's loop: it bounds itself by the same --steps budget, sleeps the
            # same interval, and stops on the same conditions this window always has.
            result = window.run(steps=goal, interval=args.interval, round_limit=goal,
                                deadline=deadline)
        else:
            result = window.summary()
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
                          if k not in ('steps', 'flow_steps', 'device', 'foreground_before',
                                       'foreground_after')},
                         ensure_ascii=False, indent=1))
        for step_record in result.get('flow_steps') or []:
            print(json.dumps({'flow': result.get('flow'), 'step': step_record['step'],
                              'kind': step_record['kind'], 'page': step_record.get('page'),
                              'token': step_record.get('token'),
                              'token_after': step_record.get('token_after'),
                              'clicks': step_record.get('clicks'),
                              'passed': step_record.get('passed'),
                              'reason': step_record.get('reason')}, ensure_ascii=False))
        for entry in result['steps']:
            print(json.dumps({'step': entry['step'], 'page_before': entry['page_before'],
                              'page_after': entry.get('page_after'),
                              'action': entry.get('action'), 'reason': entry.get('reason'),
                              'passed': entry.get('passed'),
                              'arrows': entry.get('arrows'),
                              'stopped': entry.get('stopped')}, ensure_ascii=False))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
