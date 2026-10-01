"""Execute the actual Maa Pipeline with a single Windows controller and evidence."""
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

from maa.controller import Win32Controller
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit
from recognition import Journal, LimbusRecognition, LimbusTerminal, TeamAction, InputPreflight
from maalimbus.windows_preflight import check_window, InputPermissionError
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--locale', choices=['en', 'jp'], default='en')
    parser.add_argument('--entry', default='MirrorHard')
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--live', action='store_true', required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 3600:
        parser.error('Session must be bounded to at most one hour')
    lock = ControllerLease.acquire(ROOT / 'build/controller.lock')
    directory = ROOT / ('evidence/runtime/live-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    journal = Journal(directory)
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
    windows = [w for w in Toolkit.find_desktop_windows() if w.window_name == 'LimbusCompany' and w.class_name == 'UnityWndClass']
    if len(windows) != 1:
        raise RuntimeError('Expected exactly one running LimbusCompany window')
    window = windows[0]
    try:
        identity = check_window(window.hwnd)
    except InputPermissionError as error:
        journal.record('preflight_failed', reason='windows_integrity_mismatch', **error.identity)
        (directory / 'result.json').write_text(json.dumps({'input_sent':False,
            'reason':'windows_integrity_mismatch', **error.identity},indent=2),encoding='utf-8')
        raise
    journal.record('preflight_passed', **identity)
    controller = Win32Controller(window.hwnd, MaaWin32ScreencapMethodEnum.FramePool,
                                 MaaWin32InputMethodEnum.Seize, MaaWin32InputMethodEnum.Seize)
    wait_job(controller.post_connection(), deadline=deadline)
    controller.set_screenshot_target_long_side(1920)
    resource = Resource()
    recognition = LimbusRecognition(args.locale, journal)
    resource.register_custom_recognition('limbus_scene', recognition)
    resource.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
    resource.register_custom_action('limbus_team', TeamAction(recognition))
    resource.register_custom_action('limbus_preflight',InputPreflight(recognition))
    wait_job(resource.post_bundle(ROOT / 'assets/resource/base'), timeout=20, deadline=deadline)
    wait_job(resource.post_bundle(ROOT / f'assets/resource/{args.locale}'), timeout=20, deadline=deadline)
    tasker = Tasker()
    tasker.bind(resource=resource, controller=controller)
    assert tasker.inited
    session = {'owner': 'native_cli', 'pid': os.getpid(), 'hwnd': window.hwnd,
               'started': started, 'deadline': started + args.seconds, 'evidence_directory': str(directory), 'entry': args.entry}
    (ROOT / 'build/live-session.json').write_text(json.dumps(session, indent=2), encoding='utf-8')
    print(json.dumps(session), flush=True)
    state.update(task_submitted=True, stop_confirmed=False)
    job = tasker.post_task(args.entry)
    result = wait_task(tasker, job, deadline=deadline)
    state['stop_confirmed'] = result['stop_confirmed']
    result['last_scene'] = recognition.last_scene
    (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    main()
