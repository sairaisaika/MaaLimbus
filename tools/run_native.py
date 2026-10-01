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

from maa.controller import Win32Controller
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit
from recognition import Journal, LimbusRecognition, LimbusTerminal, TeamAction, InputPreflight
from maalimbus.windows_preflight import check_window, InputPermissionError
from maalimbus.controller_lease import ControllerLease


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
    lock_path = ROOT / 'build/controller.lock'
    lock = ControllerLease.acquire(lock_path)
    directory = ROOT / ('evidence/runtime/live-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    journal = Journal(directory)
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
    assert controller.post_connection().wait().succeeded
    controller.set_screenshot_target_long_side(1920)
    resource = Resource()
    recognition = LimbusRecognition(args.locale, journal)
    resource.register_custom_recognition('limbus_scene', recognition)
    resource.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
    resource.register_custom_action('limbus_team', TeamAction(recognition))
    resource.register_custom_action('limbus_preflight',InputPreflight(recognition))
    assert resource.post_bundle(ROOT / 'assets/resource/base').wait().succeeded
    assert resource.post_bundle(ROOT / f'assets/resource/{args.locale}').wait().succeeded
    tasker = Tasker()
    tasker.bind(resource=resource, controller=controller)
    assert tasker.inited
    started = time.time()
    session = {'owner': 'native_cli', 'pid': os.getpid(), 'hwnd': window.hwnd,
               'started': started, 'deadline': started + args.seconds, 'evidence_directory': str(directory), 'entry': args.entry}
    (ROOT / 'build/live-session.json').write_text(json.dumps(session, indent=2), encoding='utf-8')
    print(json.dumps(session), flush=True)
    job = tasker.post_task(args.entry)
    timed_out = False
    try:
        while not job.done:
            if time.time() - started >= args.seconds:
                timed_out = True
                break
            time.sleep(.2)
    finally:
        if not job.done:
            tasker.post_stop().wait()
        result = {'task_succeeded': job.succeeded, 'timed_out': timed_out,
                  'last_scene': recognition.last_scene, 'verified_clear': False}
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
        lock.close()


if __name__ == '__main__':
    main()
