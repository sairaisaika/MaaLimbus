"""Execute a bounded Maa Pipeline through one Windows or Android controller."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]
from maalimbus.runtime_paths import ROOT

from maa.controller import Win32Controller, AdbController
from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum
from maalimbus.adb_preflight import foreground, controller_foreground
from maalimbus.adb_device import build, discover, input_policy
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit
from recognition import Journal, LimbusRecognition, LimbusTerminal, TeamAction, InputPreflight, ThemeObservation, DeploymentProof, BattlePlanObservation, MapObservation, BattleObservation
from recognition import StarProof,InitialGiftProof,InitialReceiptProof,DifficultyProof, MirrorLoopAction
from maalimbus.windows_preflight import check_window, InputPermissionError, process_identity
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from maalimbus.windows_controller import DEFAULT_CONTROLLER, controller_profile, native_methods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--locale', choices=['en', 'jp'], default='en')
    parser.add_argument('--entry', default='MirrorHard')
    parser.add_argument('--adb', type=Path)
    parser.add_argument('--address', help='Explicit Android serial; requires --adb')
    parser.add_argument('--observe', action='store_true', help='Capture only, never submit a task')
    parser.add_argument('--controller', default=DEFAULT_CONTROLLER,
                        choices=['windows-window', 'windows-background', 'windows'],
                        help='PI Win32 profile: window messages, background messages or foreground')
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--live', action='store_true', required=True)
    args = parser.parse_args()
    if bool(args.adb) != bool(args.address):
        parser.error('--adb and --address must be supplied together')
    if not 1 <= args.seconds <= 3600:
        parser.error('Session must be bounded to at most one hour')
    lock = ControllerLease.acquire(ROOT / 'build/controller.lock')
    directory = ROOT / ('evidence/runtime/live-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    journal = Journal(directory)
    journal.record('controller_process_identity',**process_identity(os.getpid()))
    state = {'task_submitted':False, 'stop_confirmed':True}
    try:
        result = execute(args, directory, journal, state)
    except Exception as error:
        result = {'reason':'session_failed' if state['task_submitted'] else 'session_setup_failed',
                  'error':str(error), 'input_sent':None if state['task_submitted'] else False,
                  'verified_clear':False, **state}
        # Never replace a more specific privilege/identity failure record.
        if not (directory / 'result.json').exists():
            (directory / 'result.json').write_text(json.dumps(result, indent=2),encoding='utf-8')
        raise
    finally:
        # An unconfirmed stop retains the lease until this process exits.
        if state['stop_confirmed']:
            lock.close()


def execute(args, directory, journal, state):
    started = time.time()
    deadline = time.monotonic() + args.seconds
    Library.open(args.binary, agent_server=False)
    Toolkit.init_option(ROOT / 'build/debug')
    if args.address:
        identity = {'foreground': foreground(args.adb, args.address), 'address': args.address}
        profile = {'name': 'mumu-adb', 'win32': {}}
        window = None
        # Methods come from MaaToolkit discovery (MuMu 12 native EmulatorExtras
        # screencap), never from a hand-picked combination.
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not args.observe and not allowed:
            raise RuntimeError('ADB input refused: ' + reason)
        controller = build(device, input_enabled=not args.observe)
        journal.record('preflight_passed', controller='Maa AdbController',
                       device=device, input_policy=reason, **identity)
    else:
        controller, window, profile = windows_controller(args, directory, journal)
    wait_job(controller.post_connection(), deadline=deadline)
    controller.set_screenshot_target_long_side(1920)
    wait_job(controller.post_screencap(), deadline=deadline)
    import cv2
    if not cv2.imwrite(str(directory / 'initial.png'), controller.cached_image):
        raise RuntimeError('Initial screenshot could not be saved')
    if args.observe:
        result = dict(reason='read_only_capture', input_sent=False, verified_clear=False, **state)
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    return execute_task(args, directory, journal, state, controller, window, profile, started, deadline)


def windows_controller(args, directory, journal):
    windows = [w for w in Toolkit.find_desktop_windows() if w.window_name == 'LimbusCompany' and w.class_name == 'UnityWndClass']
    if len(windows) != 1:
        raise RuntimeError('Expected exactly one running LimbusCompany window')
    window = windows[0]
    interface = ROOT / ('interface.json' if getattr(sys, 'frozen', False) else 'assets/interface.json')
    profile = controller_profile(interface, args.controller)
    try:
        identity = check_window(window.hwnd)
    except InputPermissionError as error:
        journal.record('preflight_failed', reason='windows_integrity_mismatch', **error.identity)
        (directory / 'result.json').write_text(json.dumps({'input_sent':False,
            'reason':'windows_integrity_mismatch', **error.identity},indent=2),encoding='utf-8')
        raise
    journal.record('preflight_passed', profile=profile['name'], methods=profile['win32'], **identity)
    controller = Win32Controller(window.hwnd, *native_methods(profile))
    return controller, window, profile


def execute_task(args, directory, journal, state, controller, window, profile, started, deadline):
    resource = Resource()
    recognition = LimbusRecognition(args.locale, journal)
    recognition.input_validator = (lambda: controller_foreground(controller.info)) if args.address else (lambda: check_window(window.hwnd))
    resource.register_custom_recognition('limbus_scene', recognition)
    resource.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
    resource.register_custom_action('limbus_team', TeamAction(recognition))
    resource.register_custom_action('limbus_star_proof',StarProof(recognition))
    resource.register_custom_action('limbus_initial_gift_proof',InitialGiftProof(recognition))
    resource.register_custom_action('limbus_initial_receipt_proof',InitialReceiptProof(recognition))
    resource.register_custom_action('limbus_difficulty_proof',DifficultyProof(recognition))
    preflight = InputPreflight(recognition)
    resource.register_custom_action('limbus_preflight', preflight)
    resource.register_custom_action('limbus_theme_observe',ThemeObservation(recognition))
    resource.register_custom_action('limbus_map_observe',MapObservation(recognition))
    resource.register_custom_action('limbus_battle_observe',BattleObservation(recognition))
    resource.register_custom_action('limbus_deployment_proof',DeploymentProof(recognition))
    resource.register_custom_action('limbus_battle_plan_observe',BattlePlanObservation(recognition))
    # `--entry MirrorLoop` drives the whole dungeon through this hook.
    resource.register_custom_action('limbus_mirror_loop',MirrorLoopAction(recognition))
    wait_job(resource.post_bundle(ROOT / 'assets/resource/base'), timeout=20, deadline=deadline)
    wait_job(resource.post_bundle(ROOT / f'assets/resource/{args.locale}'), timeout=20, deadline=deadline)
    tasker = Tasker()
    tasker.bind(resource=resource, controller=controller)
    assert tasker.inited
    session = {'owner': 'native_cli', 'pid': os.getpid(), 'hwnd': window.hwnd if window else None,
               'address': args.address,
               'started': started, 'deadline': started + args.seconds, 'evidence_directory': str(directory),
               'entry': args.entry, 'controller_profile': profile['name'], 'methods': profile['win32']}
    (ROOT / 'build/live-session.json').write_text(json.dumps(session, indent=2), encoding='utf-8')
    print(json.dumps(session), flush=True)
    state.update(task_submitted=True, stop_confirmed=False)
    job = tasker.post_task(args.entry)
    result = wait_task(tasker, job, deadline=deadline)
    state['stop_confirmed'] = result['stop_confirmed']
    result['last_scene'] = recognition.last_scene
    # A terminal record must include the final screen even if the scene cache
    # matched an earlier frame. Capture failure remains explicit, never a clear.
    try:
        wait_job(controller.post_screencap(),timeout=5)
        import cv2
        if not cv2.imwrite(str(directory/'terminal.png'),controller.cached_image):
            raise OSError('Terminal screenshot could not be saved')
        result['terminal_frame']='terminal.png'
    except Exception as error:
        result['terminal_capture_error']=str(error)
    (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    main()
